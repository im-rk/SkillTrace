"""
Redis Stream consumer for stream:submissions.

Kept separate from the Celery task itself (process_submission, in tasks.py)
so this loop's lifecycle isn't tied to any single task's lifecycle -- Redis
Streams' job is "get a message to a worker at least once"; Celery's own
retry/result-backend machinery then owns whether that task actually
completes. Conflating the two (e.g. acking only after full processing
succeeds) would reintroduce a loss window.

Dispatches by task NAME via celery_app.send_task rather than importing
process_submission from tasks.py directly: tasks.py's own periodic sweep
task needs to call into this module (claim_and_redeliver_pending), so this
module staying independent of tasks.py avoids a two-way import between them.
"""
import logging
import uuid
import redis.asyncio as redis

from app.core.celery_app import celery_app
from app.modules.evaluation_pipeline.queue_producer import SUBMISSIONS_STREAM

logger = logging.getLogger(__name__)

SUBMISSIONS_CONSUMER_GROUP = "bkt_workers"
# Must match the `name=` on process_submission in tasks.py.
PROCESS_SUBMISSION_TASK_NAME = "evaluation_pipeline.process_submission"


def _dispatch(log_id: str) -> None:
    celery_app.send_task(PROCESS_SUBMISSION_TASK_NAME, args=[log_id])


async def ensure_consumer_group(redis_client: redis.Redis) -> None:
    """Idempotent: safe to call from every consumer/app startup."""
    try:
        await redis_client.xgroup_create(SUBMISSIONS_STREAM, SUBMISSIONS_CONSUMER_GROUP, mkstream=True, id="0")
    except redis.ResponseError as e:
        if "BUSYGROUP" not in str(e):
            raise


async def consume_submissions_loop(redis_client: redis.Redis, consumer_name: str | None = None) -> None:
    await ensure_consumer_group(redis_client)
    consumer_name = consumer_name or f"consumer-{uuid.uuid4().hex[:8]}"
    while True:
        messages = await redis_client.xreadgroup(
            SUBMISSIONS_CONSUMER_GROUP, consumer_name, {SUBMISSIONS_STREAM: ">"}, count=10, block=2000
        )
        for _stream_name, entries in messages:
            if not entries:
                continue
            message_ids = []
            for message_id, fields in entries:
                _dispatch(fields["log_id"])
                message_ids.append(message_id)
            # Ack right after successful dispatch, not after processing
            # completes -- see module docstring. One batched call per read.
            await redis_client.xack(SUBMISSIONS_STREAM, SUBMISSIONS_CONSUMER_GROUP, *message_ids)


async def claim_and_redeliver_pending(
    redis_client: redis.Redis, min_idle_ms: int = 30_000, count: int = 50
) -> int:
    """Reclaims messages that have sat unacked in the Pending Entries List for
    longer than min_idle_ms -- the consumer likely crashed before XACK. This,
    not the initial XREADGROUP read, is the actual mechanism behind "zero lost
    submissions"; run periodically (worker/beat_schedule.py), not just as a
    one-off test utility."""
    await ensure_consumer_group(redis_client)
    cursor = "0-0"
    claimed_total = 0
    while True:
        cursor, messages, _deleted = await redis_client.xautoclaim(
            SUBMISSIONS_STREAM,
            SUBMISSIONS_CONSUMER_GROUP,
            "recovery-sweep",
            min_idle_ms,
            start_id=cursor,
            count=count,
        )
        if not messages:
            break
        message_ids = []
        for message_id, fields in messages:
            _dispatch(fields["log_id"])
            message_ids.append(message_id)
        await redis_client.xack(SUBMISSIONS_STREAM, SUBMISSIONS_CONSUMER_GROUP, *message_ids)
        claimed_total += len(message_ids)
        if cursor == "0-0":
            break
    return claimed_total
