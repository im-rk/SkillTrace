"""
Redis distributed lock wrapper for concurrency control during exam start.
"""
import redis.asyncio as redis


def _lock_key(user_id: str, exam_id: str) -> str:
    return f"lock:exam_start:{user_id}:{exam_id}"


async def acquire_start_lock(redis_client: redis.Redis, user_id: str, exam_id: str, ttl_ms: int = 5000) -> bool:
    """Atomic SET NX PX: acquiring and setting the TTL in one operation avoids a
    crash window where the lock would exist without an expiry (SETNX + EXPIRE is not atomic)."""
    return bool(await redis_client.set(_lock_key(user_id, exam_id), "1", nx=True, px=ttl_ms))


async def release_start_lock(redis_client: redis.Redis, user_id: str, exam_id: str) -> None:
    """Best-effort; the TTL is the real safety net if this is never called."""
    await redis_client.delete(_lock_key(user_id, exam_id))
