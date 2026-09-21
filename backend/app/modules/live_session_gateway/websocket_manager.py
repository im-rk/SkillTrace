"""
Per-instance WebSocket connection registry, plus the Redis Pub/Sub bridge that
lets a broadcast published from any backend instance reach connections held by
every other instance. See docs/adr/0010-websocket-authorization-ordering.md
for why registration only ever happens after a successful pre-accept check.
"""
import asyncio
import json
import logging
from fastapi import WebSocket
import redis.asyncio as redis

logger = logging.getLogger(__name__)

EXAM_EVENTS_CHANNEL_PREFIX = "exam_events:"


class ConnectionManager:
    """LOCAL to this process -- a single instance only ever knows about the
    connections it is itself holding. Cross-instance reach comes from Redis
    Pub/Sub (see redis_subscriber_loop below), never from this registry
    directly."""

    def __init__(self):
        self._connections: dict[str, WebSocket] = {}  # session_id -> websocket
        self._exam_sessions: dict[str, set[str]] = {}  # exam_id -> {session_id, ...}

    async def connect(self, session_id: str, exam_id: str, websocket: WebSocket) -> None:
        self._connections[session_id] = websocket
        self._exam_sessions.setdefault(exam_id, set()).add(session_id)

    async def disconnect(self, session_id: str, exam_id: str) -> None:
        self._connections.pop(session_id, None)
        sessions = self._exam_sessions.get(exam_id)
        if sessions is not None:
            sessions.discard(session_id)
            if not sessions:
                self._exam_sessions.pop(exam_id, None)

    async def send_to_session(self, session_id: str, message: dict) -> bool:
        ws = self._connections.get(session_id)
        if ws is None:
            return False  # this instance doesn't hold this connection
        try:
            await ws.send_json(message)
        except Exception:  # noqa: BLE001 -- a dead socket must not break delivery to everyone else
            logger.warning("Dropping dead WebSocket for session %s", session_id)
            self._connections.pop(session_id, None)
            return False
        return True

    async def broadcast_to_exam(self, exam_id: str, message: dict) -> int:
        """Relays to every LOCAL connection for this exam_id. Returns how many
        local connections it reached (0 is normal -- this instance may hold
        none of the exam's connections)."""
        session_ids = list(self._exam_sessions.get(exam_id, ()))
        delivered = 0
        for session_id in session_ids:
            if await self.send_to_session(session_id, message):
                delivered += 1
        return delivered


connection_manager = ConnectionManager()


async def broadcast_exam_event(redis_client: redis.Redis, exam_id: str, event: dict) -> None:
    """Publishing side -- called from any instance (an instructor action, a
    Beat task noticing an exam ended). Reaches every instance's local
    connections via redis_subscriber_loop below, not directly."""
    channel = f"{EXAM_EVENTS_CHANNEL_PREFIX}{exam_id}"
    await redis_client.publish(channel, json.dumps(event))


async def redis_subscriber_loop(redis_client: redis.Redis, manager: ConnectionManager) -> None:
    """One pass: pattern-subscribes to all exams' channels at once (simpler
    than per-exam dynamic subscription -- the per-exam filtering already
    happens locally in broadcast_to_exam) and relays until the connection
    drops or the task is cancelled. Callers that need this to run for the
    life of the process should use run_subscriber_forever below, not
    reimplement retry-on-crash themselves."""
    pubsub = redis_client.pubsub()
    await pubsub.psubscribe(f"{EXAM_EVENTS_CHANNEL_PREFIX}*")
    try:
        async for message in pubsub.listen():
            if message["type"] != "pmessage":
                continue
            try:
                exam_id = message["channel"].split(":", 1)[-1]
                event = json.loads(message["data"])
            except (ValueError, TypeError) as e:
                logger.warning("Malformed exam_events message, dropping: %s", e)
                continue
            if isinstance(event, dict) and event.get("session_id"):
                await manager.send_to_session(event["session_id"], event)  # targeted event
            else:
                await manager.broadcast_to_exam(exam_id, event)
    finally:
        await pubsub.punsubscribe(f"{EXAM_EVENTS_CHANNEL_PREFIX}*")
        await pubsub.aclose()


async def run_subscriber_forever(redis_client: redis.Redis, manager: ConnectionManager) -> None:
    """The supervised, run-for-the-life-of-the-process entry point: if
    redis_subscriber_loop dies unexpectedly (e.g. a dropped Redis connection),
    every broadcast silently stops reaching this instance with no obvious
    symptom -- restart rather than let that happen. This owns its own
    resilience; callers (app startup) just need to run this as a background
    task, no retry logic of their own."""
    while True:
        try:
            await redis_subscriber_loop(redis_client, manager)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("redis_subscriber_loop crashed, restarting")
            await asyncio.sleep(1)
