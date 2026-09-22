"""
Fixed-window rate limiting on Redis. Hand-rolled (a dozen lines) rather than a
library: one INCR per request is all this needs.

ponytail: fixed window allows up to 2x the limit across a window boundary. Move
to a sliding-window log / token bucket if that burst ever matters.
"""
import logging

import redis.asyncio as redis
from fastapi import HTTPException, status

logger = logging.getLogger(__name__)


async def hit(redis_client: redis.Redis, key: str, limit: int, window_seconds: int) -> tuple[bool, int]:
    """Counts one request against `key`. Returns (allowed, seconds_until_the_window_resets).

    SET NX EX + INCR in one transaction: the window's expiry is set atomically with
    the first hit, so a crash can never leave a counter that never expires.
    """
    full_key = f"ratelimit:{key}"
    pipe = redis_client.pipeline(transaction=True)
    pipe.set(full_key, 0, ex=window_seconds, nx=True)
    pipe.incr(full_key)
    pipe.ttl(full_key)
    _, count, ttl = await pipe.execute()
    return count <= limit, max(ttl, 1)


async def enforce(redis_client: redis.Redis, key: str, limit: int, window_seconds: int = 60) -> None:
    """Raises 429 (with Retry-After) once `key` exceeds `limit` in the window. Fails OPEN if Redis
    is unreachable: a limiter outage should degrade to "unlimited", not take the API down."""
    try:
        allowed, retry_after = await hit(redis_client, key, limit, window_seconds)
    except redis.RedisError:
        logger.warning("Rate limiter unavailable (Redis error); allowing request", exc_info=True)
        return
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests, slow down",
            headers={"Retry-After": str(retry_after)},
        )
