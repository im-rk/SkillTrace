"""
Redis async client pool management.
"""
from typing import Optional
import redis.asyncio as redis
from app.core.config import settings

_redis_pool: Optional[redis.Redis] = None


def get_redis() -> redis.Redis:
    """
    Returns or initializes the singleton async Redis connection pool.
    """
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis_pool


async def close_redis() -> None:
    """
    Closes the async Redis connection pool.
    """
    global _redis_pool
    if _redis_pool is not None:
        await _redis_pool.aclose()
        _redis_pool = None
