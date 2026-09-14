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

engine = create_async_engine(TEST_DATABASE_URL, echo=False, poolclass=sa.pool.NullPool)
TestingSessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_db():
    async with engine.begin() as conn:
        await conn.execute(sa.text("DROP SCHEMA public CASCADE;"))
        await conn.execute(sa.text("CREATE SCHEMA public;"))
        await conn.execute(sa.text("CREATE EXTENSION IF NOT EXISTS citext;"))
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(sa.text("CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) NOT NULL, PRIMARY KEY (version_num));"))
        await conn.execute(sa.text("INSERT INTO alembic_version (version_num) VALUES ('a58364843b87');"))
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