"""
Redis distributed lock wrapper for concurrency control during exam start.
"""
import logging
import time
import uuid

import redis.asyncio as redis

logger = logging.getLogger(__name__)

LOCK_CONTENTION_KEY = "metrics:lock_contention"
CONTENTION_WINDOW_SECONDS = 3600


def _lock_key(user_id: str, exam_id: str) -> str:
    return f"lock:exam_start:{user_id}:{exam_id}"


async def acquire_start_lock(redis_client: redis.Redis, user_id: str, exam_id: str, ttl_ms: int = 5000) -> bool:
    """Atomic SET NX PX: acquiring and setting the TTL in one operation avoids a
    crash window where the lock would exist without an expiry (SETNX + EXPIRE is not atomic)."""
    acquired = bool(await redis_client.set(_lock_key(user_id, exam_id), "1", nx=True, px=ttl_ms))
    if not acquired:
        await record_lock_contention(redis_client)
    return acquired


async def record_lock_contention(redis_client: redis.Redis) -> None:
    """One sorted-set entry per refused acquire, scored by time, so "last hour" is an exact
    range count. Best-effort: a metrics hiccup must never fail the exam-start request."""
    now = time.time()
    try:
        pipe = redis_client.pipeline(transaction=True)
        pipe.zadd(LOCK_CONTENTION_KEY, {uuid.uuid4().hex: now})
        pipe.zremrangebyscore(LOCK_CONTENTION_KEY, 0, now - CONTENTION_WINDOW_SECONDS)  # keeps the set bounded
        pipe.expire(LOCK_CONTENTION_KEY, 2 * CONTENTION_WINDOW_SECONDS)
        await pipe.execute()
    except redis.RedisError:
        logger.warning("Could not record lock contention", exc_info=True)


async def count_lock_contention_last_hour(redis_client: redis.Redis) -> int:
    return await redis_client.zcount(LOCK_CONTENTION_KEY, time.time() - CONTENTION_WINDOW_SECONDS, "+inf")


async def release_start_lock(redis_client: redis.Redis, user_id: str, exam_id: str) -> None:
    """Best-effort; the TTL is the real safety net if this is never called."""
    await redis_client.delete(_lock_key(user_id, exam_id))
