import os

# Tests run against their OWN database and Redis logical DBs, never the dev
# stack's. This must happen before any `app.*` import: pydantic Settings reads
# the environment once at import time, and the app's module-level engine is
# built from it.
_TEST_DB_NAME = os.environ.get("TEST_DB_NAME", "skilltrace_test")
_DEV_DSN = os.environ.get("DATABASE_URL", "postgresql+asyncpg://user:password@localhost:15432/skilltrace")
_BASE_DSN = _DEV_DSN.rsplit("/", 1)[0]
os.environ["DATABASE_URL"] = f"{_BASE_DSN}/{_TEST_DB_NAME}"
os.environ["SYNC_DATABASE_URL"] = os.environ["DATABASE_URL"].replace("+asyncpg", "+psycopg")
_REDIS_BASE = os.environ.get("REDIS_URL", "redis://localhost:16379/0").rsplit("/", 1)[0]
os.environ["REDIS_URL"] = f"{_REDIS_BASE}/5"
os.environ["CELERY_BROKER_URL"] = f"{_REDIS_BASE}/6"
os.environ["CELERY_RESULT_BACKEND"] = f"{_REDIS_BASE}/7"
os.environ["BCRYPT_ROUNDS"] = "4"
# Off by default so ordinary tests never trip (or share) a limiter bucket; the rate-limit tests switch it on.
os.environ["RATE_LIMIT_ENABLED"] = "false"

import uuid
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from typing import AsyncGenerator
import redis.asyncio as aioredis

import app.modules.iam.models
import app.modules.quiz_engine.models
import app.modules.question_bank.models
import app.modules.scheduling.models
import app.modules.enrollment.models
import app.modules.live_session_gateway.models
import app.modules.evaluation_pipeline.models
from app.main import app as fastapi_app
from app.core.db.base import Base
from app.core.db.session import get_db
from app.core.config import settings
from app.core.celery_app import celery_app
from app.modules.iam.models import User, UserRole
from app.modules.iam.service import create_access_token

TEST_DATABASE_URL = settings.DATABASE_URL
assert TEST_DATABASE_URL.rsplit("/", 1)[1] == _TEST_DB_NAME, "tests must never run against a non-test database"

engine = create_async_engine(TEST_DATABASE_URL, echo=False, poolclass=sa.pool.NullPool)
TestingSessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)


async def _ensure_test_database_exists() -> None:
    admin = create_async_engine(f"{_BASE_DSN}/postgres", isolation_level="AUTOCOMMIT", poolclass=sa.pool.NullPool)
    async with admin.connect() as conn:
        exists = await conn.scalar(sa.text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": _TEST_DB_NAME})
        if not exists:
            await conn.execute(sa.text(f'CREATE DATABASE "{_TEST_DB_NAME}"'))
    await admin.dispose()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_db():
    await _ensure_test_database_exists()
    async with engine.begin() as conn:
        await conn.execute(sa.text("DROP SCHEMA public CASCADE;"))
        await conn.execute(sa.text("CREATE SCHEMA public;"))
        await conn.execute(sa.text("CREATE EXTENSION IF NOT EXISTS citext;"))
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(sa.text("CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) NOT NULL, PRIMARY KEY (version_num));"))
        await conn.execute(sa.text("INSERT INTO alembic_version (version_num) VALUES ('3c1f0a7d9e42');"))
        # mv_exam_results is raw SQL in the migration, not a mapped model, so
        # Base.metadata.create_all doesn't create it -- must mirror it here.
        await conn.execute(sa.text("""
            CREATE MATERIALIZED VIEW mv_exam_results AS
            SELECT
                es.exam_id,
                es.student_id,
                u.display_name AS student_name,
                COUNT(r.id) AS questions_answered,
                SUM(r.points_awarded) AS total_score,
                MAX(r.answered_at) AS last_activity,
                AVG(r.mastery_after) AS average_mastery
            FROM exam_sessions es
            JOIN users u ON es.student_id = u.id
            LEFT JOIN responses r ON r.exam_session_id = es.id
            WHERE es.status IN ('submitted', 'auto_submitted')
            GROUP BY es.exam_id, es.student_id, u.display_name;
        """))
        await conn.execute(sa.text("CREATE UNIQUE INDEX idx_mv_exam_results_pk ON mv_exam_results(exam_id, student_id);"))
    yield
    async with engine.begin() as conn:
        await conn.execute(sa.text("DROP SCHEMA public CASCADE;"))
        await conn.execute(sa.text("CREATE SCHEMA public;"))
    await engine.dispose()


@pytest_asyncio.fixture(scope="session", autouse=True)
def configure_celery_eager():
    """Configure Celery to run in eager mode for testing."""
    celery_app.conf.update(
        task_always_eager=True,
        task_eager_propagates=True,
    )
    yield
    celery_app.conf.update(
        task_always_eager=False,
        task_eager_propagates=False,
    )


@pytest_asyncio.fixture(autouse=True)
async def _reset_global_redis_client():
    """app.core.redis_client keeps one process-wide async client. It gets bound to
    whichever event loop first uses it -- pytest's, or a TestClient's own -- and
    reusing it from another loop breaks (pubsub crashes, "attached to a different
    loop"). Start every test with none."""
    from app.core.redis_client import close_redis

    await close_redis()
    yield
    await close_redis()


@pytest_asyncio.fixture
async def redis_client():
    """Provides async Redis test client."""
    client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    yield client
    await client.aclose()


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator:
    async with TestingSessionLocal() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(db_session):
    async def override_get_db():
        yield db_session
    
    fastapi_app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    fastapi_app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def make_user(db_session: AsyncSession):
    """Creates a persisted user with the given role and returns (auth_headers, user_id)."""

    async def _make(role: UserRole) -> tuple[dict, str]:
        user = User(
            email=f"{role.value}_{uuid.uuid4().hex[:8]}@example.com",
            display_name=role.value,
            password_hash="x",
            role=role,
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        token = create_access_token(data={"sub": str(user.id), "role": role.value})
        return {"Authorization": f"Bearer {token}"}, str(user.id)

    return _make