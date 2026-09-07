import pytest
from httpx import AsyncClient
from app.core.celery_app import ping


@pytest.mark.asyncio
async def test_health_endpoint(client: AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_redis_connectivity(redis_client):
    is_alive = await redis_client.ping()
    assert is_alive is True


def test_celery_task_execution():
    res = ping.delay()
    assert res.get() == "pong"
