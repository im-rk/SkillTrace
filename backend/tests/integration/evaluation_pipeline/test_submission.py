import time
import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.evaluation_pipeline import repository as queue_repository
from app.modules.evaluation_pipeline.models import SubmissionQueueLog, SubmissionStatus
from app.modules.evaluation_pipeline.queue_producer import SUBMISSIONS_STREAM
from app.modules.evaluation_pipeline.stream_consumer import ensure_consumer_group
from app.modules.evaluation_pipeline.tasks import _process_submission
from app.modules.quiz_engine.models import Response
from tests.integration.evaluation_pipeline.conftest import submit_for_setup


@pytest.mark.asyncio
async def test_case_1_submit_answer_happy_path(client: AsyncClient, db_session: AsyncSession, submission_setup):
    response = await client.post(
        f"/exam-sessions/{submission_setup['exam_session_id']}/submit-answer",
        json={"question_id": submission_setup["question_id"], "answer": submission_setup["correct_answer"]},
        headers=submission_setup["student_headers"],
    )
    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "accepted"
    log_id = uuid.UUID(data["log_id"])

    log_entry = await queue_repository.get_log_entry(db_session, log_id)
    assert log_entry.status == SubmissionStatus.pending

    await _process_submission(str(log_id))

    await db_session.refresh(log_entry)
    assert log_entry.status == SubmissionStatus.completed


@pytest.mark.asyncio
async def test_case_2_consumer_produces_correct_bkt_mastery(
    db_session: AsyncSession, redis_client, submission_setup
):
    """Same reference computation as Phase 3's worked example (P(L0)=0.3,
    default params): a correct answer moves mastery 0.30 -> ~0.7098."""
    log_entry = await submit_for_setup(db_session, redis_client, submission_setup, submission_setup["correct_answer"])

    await _process_submission(str(log_entry.id))

    result = await db_session.execute(
        select(Response).where(Response.question_id == uuid.UUID(submission_setup["question_id"]))
    )
    response = result.scalars().one()
    assert response.is_correct is True
    assert float(response.mastery_before) == pytest.approx(0.3, rel=1e-4)
    assert float(response.mastery_after) == pytest.approx(0.709756, rel=1e-4)
    assert response.points_awarded == 2
    assert response.exam_session_id == uuid.UUID(submission_setup["exam_session_id"])


@pytest.mark.asyncio
async def test_case_5_submit_response_time_constant_under_backlog(
    db_session: AsyncSession, redis_client, submission_setup
):
    for _ in range(500):
        await redis_client.xadd(SUBMISSIONS_STREAM, {"log_id": str(uuid.uuid4())})

    start = time.monotonic()
    await submit_for_setup(db_session, redis_client, submission_setup, submission_setup["wrong_answer"])
    elapsed = time.monotonic() - start
    assert elapsed < 1.0, f"submit_answer took {elapsed:.3f}s with a 500-message backlog"


@pytest.mark.asyncio
async def test_case_6_submit_for_nonexistent_session_404_never_queued(
    client: AsyncClient, db_session: AsyncSession, submission_setup
):
    before = (await db_session.execute(select(SubmissionQueueLog))).scalars().all()

    response = await client.post(
        f"/exam-sessions/{uuid.uuid4()}/submit-answer",
        json={"question_id": submission_setup["question_id"], "answer": "x"},
        headers=submission_setup["student_headers"],
    )
    assert response.status_code == 404

    after = (await db_session.execute(select(SubmissionQueueLog))).scalars().all()
    assert len(after) == len(before), "A 404 at the synchronous layer must never create a queue row"


@pytest.mark.asyncio
async def test_case_6b_submit_for_someone_elses_session_403(
    client: AsyncClient, submission_setup, make_user
):
    from app.modules.iam.models import UserRole

    other_headers, _ = await make_user(UserRole.student)
    response = await client.post(
        f"/exam-sessions/{submission_setup['exam_session_id']}/submit-answer",
        json={"question_id": submission_setup["question_id"], "answer": "x"},
        headers=other_headers,
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_case_7_ensure_consumer_group_is_idempotent(redis_client):
    await ensure_consumer_group(redis_client)
    await ensure_consumer_group(redis_client)  # must not raise


@pytest.mark.asyncio
async def test_submission_status_reflects_pending_then_completed(client: AsyncClient, submission_setup):
    """Backs the frontend's "submitted, being processed" vs "confirmed
    processed" distinction: the submit endpoint itself only ever returns 202."""
    submit_res = await client.post(
        f"/exam-sessions/{submission_setup['exam_session_id']}/submit-answer",
        json={"question_id": submission_setup["question_id"], "answer": submission_setup["correct_answer"]},
        headers=submission_setup["student_headers"],
    )
    log_id = submit_res.json()["log_id"]

    pending_res = await client.get(f"/submissions/{log_id}", headers=submission_setup["student_headers"])
    assert pending_res.status_code == 200
    assert pending_res.json()["status"] == "pending"

    await _process_submission(log_id)

    completed_res = await client.get(f"/submissions/{log_id}", headers=submission_setup["student_headers"])
    assert completed_res.json()["status"] == "completed"


@pytest.mark.asyncio
async def test_submission_status_for_someone_elses_submission_403(client: AsyncClient, submission_setup, make_user):
    from app.modules.iam.models import UserRole

    submit_res = await client.post(
        f"/exam-sessions/{submission_setup['exam_session_id']}/submit-answer",
        json={"question_id": submission_setup["question_id"], "answer": "b"},
        headers=submission_setup["student_headers"],
    )
    log_id = submit_res.json()["log_id"]

    other_headers, _ = await make_user(UserRole.student)
    res = await client.get(f"/submissions/{log_id}", headers=other_headers)
    assert res.status_code == 403
