"""
Chaos test for kill-worker-mid-processing to ensure zero dropped submissions.

Verified at two layers, mirroring Phase 8's "split-half" approach to testing
cross-instance broadcast (documented there as a deliberate simplification):

  1. The idempotency guard itself -- process_submission's DB-level
     correctness under redelivery. Calling the actual processing coroutine
     twice for the same log_id must produce exactly one `responses` row.
  2. The Redis-level PEL (Pending Entries List) reclaim mechanism --
     XAUTOCLAIM genuinely reclaims a message that was read via XREADGROUP
     but never XACKed (the crash scenario), independent of Celery dispatch.

Why not drive this fully through Celery's .delay()? This test suite runs
Celery in eager mode (task_always_eager=True), so .delay() executes the task
body synchronously, in-process -- and process_submission's body calls
asyncio.run() (via app.core.async_task.run_async) to bridge into async
application code. Calling that from inside an already-running
pytest-asyncio event loop would raise "asyncio.run() cannot be called from a
running event loop". The phase spec itself anticipates this: its own chaos
test pseudocode calls `process_submission(log_id)` directly rather than via
`.delay()`, "for test determinism". Layer 3 below (claim_and_redeliver_pending)
sidesteps the same nesting problem by mocking the dispatch call, verifying
its own orchestration (find pending -> dispatch -> ack) without invoking the
real task body a second time.
"""
import uuid
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.evaluation_pipeline.queue_producer import SUBMISSIONS_STREAM
from app.modules.evaluation_pipeline.stream_consumer import (
    SUBMISSIONS_CONSUMER_GROUP,
    claim_and_redeliver_pending,
    ensure_consumer_group,
)
from app.modules.evaluation_pipeline.tasks import _process_submission
from app.modules.quiz_engine.models import Response
from tests.integration.evaluation_pipeline.conftest import submit_for_setup as _submit


@pytest.mark.asyncio
@pytest.mark.parametrize("run", range(5))
async def test_worker_crash_mid_processing_results_in_exactly_once_processing(
    run, db_session: AsyncSession, redis_client, submission_setup
):
    log_entry = await _submit(db_session, redis_client, submission_setup, submission_setup["correct_answer"])

    # A worker completing processing normally.
    await _process_submission(str(log_entry.id))

    result = await db_session.execute(select(Response).where(Response.question_id == uuid.UUID(submission_setup["question_id"])))
    assert len(result.scalars().all()) == 1

    # Simulate the crash-just-before-XACK redelivery: the same log_id is
    # handed to the processor again, exactly as XAUTOCLAIM would after a
    # worker died between finishing the DB commit and acking the stream.
    await _process_submission(str(log_entry.id))

    result = await db_session.execute(select(Response).where(Response.question_id == uuid.UUID(submission_setup["question_id"])))
    assert len(result.scalars().all()) == 1, "Idempotency guard must prevent a duplicate responses row"


@pytest.mark.asyncio
async def test_pending_entry_is_reclaimable_after_crash_without_ack(
    db_session: AsyncSession, redis_client, submission_setup
):
    log_entry = await _submit(db_session, redis_client, submission_setup, submission_setup["correct_answer"])

    await ensure_consumer_group(redis_client)
    # Read it into a consumer's PEL, but never XACK -- simulates a worker
    # that picked the message up then crashed before dispatch/ack.
    read = await redis_client.xreadgroup(
        SUBMISSIONS_CONSUMER_GROUP, "crashed-worker", {SUBMISSIONS_STREAM: ">"}, count=10
    )
    read_ids = {message_id for _stream, entries in read for message_id, _fields in entries}
    assert any(
        fields.get("log_id") == str(log_entry.id) for _stream, entries in read for _mid, fields in entries
    ), "Test setup: the submitted message must actually be in this batch"

    _cursor, claimed, _deleted = await redis_client.xautoclaim(
        SUBMISSIONS_STREAM, SUBMISSIONS_CONSUMER_GROUP, "recovery-sweep", min_idle_time=0, start_id="0-0"
    )
    claimed_ids = {message_id for message_id, _fields in claimed}
    assert read_ids & claimed_ids, "An unacked message must be reclaimable via XAUTOCLAIM"


@pytest.mark.asyncio
async def test_claim_and_redeliver_pending_redispatches_and_acks(
    mocker, db_session: AsyncSession, redis_client, submission_setup
):
    log_entry = await _submit(db_session, redis_client, submission_setup, submission_setup["correct_answer"])

    await ensure_consumer_group(redis_client)
    await redis_client.xreadgroup(
        SUBMISSIONS_CONSUMER_GROUP, "crashed-worker", {SUBMISSIONS_STREAM: ">"}, count=10
    )  # left unacked, simulating a crash

    send_task = mocker.patch("app.modules.evaluation_pipeline.stream_consumer.celery_app.send_task")
    claimed_count = await claim_and_redeliver_pending(redis_client, min_idle_ms=0)

    assert claimed_count >= 1
    send_task.assert_any_call("evaluation_pipeline.process_submission", args=[str(log_entry.id)])
