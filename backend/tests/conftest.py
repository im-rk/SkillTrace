import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from typing import AsyncGenerator
import redis.asyncio as aioredis

import app.modules.iam.models
from app.main import app as fastapi_app
from app.core.db.base import Base
from app.core.db.session import get_db
from app.core.config import settings
from app.core.celery_app import celery_app

TEST_DATABASE_URL = settings.DATABASE_URL

engine = create_async_engine(TEST_DATABASE_URL, echo=False, poolclass=sa.pool.NullPool)
TestingSessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_db():
    async with engine.begin() as conn:
        await conn.execute(sa.text("DROP SCHEMA public CASCADE;"))
        await conn.execute(sa.text("CREATE SCHEMA public;"))
        await conn.execute(sa.text("CREATE EXTENSION IF NOT EXISTS citext;"))
        await conn.run_sync(Base.metadata.create_all)
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