"""
Cross-instance broadcast, tested as two independent halves rather than with
two real backend processes (the phase spec's documented simplification):

  1. broadcast_exam_event() really publishes to the exam_events:{exam_id}
     Redis channel -- verified with a raw Redis subscriber here, independent
     of our own subscriber code.
  2. redis_subscriber_loop(), given a message arriving on that channel,
     correctly relays it via ConnectionManager.broadcast_to_exam().

Together these prove the same property a real 2-process test would: instance
A's publish reaches instance B's local connections purely through Redis, with
no direct in-process call between the publish and relay code paths -- each
half is verified against the actual Redis service, never against each other.
"""
import asyncio
import json
import uuid
import pytest
import redis.asyncio as aioredis

from app.core.config import settings
from app.modules.live_session_gateway.websocket_manager import (
    ConnectionManager,
    broadcast_exam_event,
    redis_subscriber_loop,
)


@pytest.mark.asyncio
async def test_broadcast_exam_event_publishes_to_redis():
    exam_id = str(uuid.uuid4())
    subscriber = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    pubsub = subscriber.pubsub()
    await pubsub.subscribe(f"exam_events:{exam_id}")
    await pubsub.get_message(timeout=2)  # the subscribe confirmation itself

    publisher = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    event = {"type": "time_up", "exam_id": exam_id}
    await broadcast_exam_event(publisher, exam_id, event)

    message = None
    for _ in range(20):
        message = await pubsub.get_message(timeout=1)
        if message and message["type"] == "message":
            break
        message = None

    await pubsub.aclose()
    await publisher.aclose()
    await subscriber.aclose()

    assert message is not None, "broadcast_exam_event did not publish to the expected channel"
    assert json.loads(message["data"]) == event


@pytest.mark.asyncio
async def test_redis_subscriber_loop_relays_to_local_connection_manager():
    exam_id = str(uuid.uuid4())
    manager = ConnectionManager()
    delivered: list[tuple[str, dict]] = []

    async def fake_broadcast(eid: str, message: dict) -> int:
        delivered.append((eid, message))
        return 0

    manager.broadcast_to_exam = fake_broadcast  # type: ignore[method-assign]

    redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    loop_task = asyncio.create_task(redis_subscriber_loop(redis_client, manager))
    await asyncio.sleep(0.3)  # let psubscribe register before publishing

    event = {"type": "time_up", "exam_id": exam_id}
    await redis_client.publish(f"exam_events:{exam_id}", json.dumps(event))

    for _ in range(20):
        if delivered:
            break
        await asyncio.sleep(0.1)

    loop_task.cancel()
    try:
        await loop_task
    except asyncio.CancelledError:
        pass
    await redis_client.aclose()

    assert delivered == [(exam_id, event)]
