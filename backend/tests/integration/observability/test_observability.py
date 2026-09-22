"""
Phase 13: correlated logging, the metrics endpoint, and rate limiting.
"""
import logging
import uuid

import pytest
import redis.asyncio as aioredis

from app.core.config import settings
from app.core.logging import RequestIdFilter
from app.modules.evaluation_pipeline.models import SubmissionQueueLog, SubmissionStatus
from app.modules.evaluation_pipeline.queue_producer import SUBMISSIONS_STREAM
from app.modules.evaluation_pipeline.stream_consumer import PROCESS_SUBMISSION_TASK_NAME, _dispatch
from app.modules.evaluation_pipeline.tasks import _process_submission_as, process_submission
from app.modules.iam.models import UserRole
from app.modules.live_session_gateway.websocket_manager import connection_manager
from app.modules.question_bank.models import DifficultyLevel, Question, QuestionType
from app.modules.scheduling.locking import acquire_start_lock, release_start_lock


class _Capture(logging.Handler):
    """Collects (request_id, logger name, message) for every record, tagged by the same
    filter the real handler uses."""

    def __init__(self):
        super().__init__(logging.DEBUG)
        self.addFilter(RequestIdFilter())
        self.lines: list[tuple[str, str, str]] = []

    def emit(self, record):
        self.lines.append((record.request_id, record.name, record.getMessage()))


@pytest.fixture
def captured_logs():
    handler = _Capture()
    root = logging.getLogger()
    previous_level = root.level
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    yield handler
    root.removeHandler(handler)
    root.setLevel(previous_level)


# --- correlation ids ----------------------------------------------------------

@pytest.mark.asyncio
async def test_request_id_is_echoed_generated_and_sanitised(client):
    echoed = await client.get("/health", headers={"X-Request-ID": "trace-me.123"})
    assert echoed.headers["x-request-id"] == "trace-me.123"

    generated = await client.get("/health")
    assert len(generated.headers["x-request-id"]) == 32

    for hostile in ("has spaces", "x" * 100, "semi;colon"):
        replaced = await client.get("/health", headers={"X-Request-ID": hostile})
        assert replaced.headers["x-request-id"] != hostile  # never reflected into logs verbatim


@pytest.mark.asyncio
async def test_case_1_one_request_id_traces_a_submission_across_api_producer_consumer_and_worker(
    client, redis_client, mocker, captured_logs, started_exam
):
    rid = f"trace-{uuid.uuid4().hex[:12]}"
    res = await client.post(
        f"/exam-sessions/{started_exam['session_id']}/submit-answer",
        json={"question_id": started_exam["question_ids"][0], "answer": "b"},
        headers={**started_exam["student_headers"], "X-Request-ID": rid},
    )
    assert res.status_code == 202, res.text
    assert res.headers["x-request-id"] == rid
    log_id = res.json()["log_id"]

    # 1. API + queue producer: same id in the access line and the producer's own line.
    api_lines = [(name, msg) for r, name, msg in captured_logs.lines if r == rid]
    assert any(name == "skilltrace.access" and "submit-answer" in msg for name, msg in api_lines)
    assert any(name.endswith("queue_producer") and log_id in msg for name, msg in api_lines)

    # 2. The id travels in the stream message itself.
    entry = next(fields for _id, fields in await redis_client.xrevrange(SUBMISSIONS_STREAM, count=50) if fields["log_id"] == log_id)
    assert entry["request_id"] == rid

    # 3. Stream consumer -> Celery: logs under the id and forwards it as a task kwarg.
    send_task = mocker.patch("app.modules.evaluation_pipeline.stream_consumer.celery_app.send_task")
    _dispatch(entry["log_id"], entry.get("request_id"))
    send_task.assert_called_once_with(PROCESS_SUBMISSION_TASK_NAME, args=[log_id], kwargs={"request_id": rid})
    assert any(r == rid and name.endswith("stream_consumer") for r, name, _ in captured_logs.lines)

    # 4. The Celery task entry point hands the id to the coroutine that grades...
    run = mocker.patch("app.modules.evaluation_pipeline.tasks._process_submission_as", new=mocker.MagicMock(return_value="coro"))
    run_async = mocker.patch("app.modules.evaluation_pipeline.tasks.run_async")
    process_submission.run(log_id, request_id=rid)
    run.assert_called_once_with(log_id, rid)
    run_async.assert_called_once_with("coro")

    # ...which binds it for the duration of grading, so the worker's own log line carries it.
    await _process_submission_as(log_id, rid)
    assert any(r == rid and name.endswith("evaluation_pipeline.tasks") and log_id in msg for r, name, msg in captured_logs.lines)


# --- metrics ------------------------------------------------------------------

async def _metrics(client, headers) -> dict:
    res = await client.get("/admin/metrics", headers=headers)
    assert res.status_code == 200, res.text
    return res.json()


@pytest.mark.asyncio
async def test_case_2_metrics_report_queue_depth_and_lock_contention_exactly(
    client, db_session, redis_client, make_user, started_exam
):
    admin_headers, _ = await make_user(UserRole.admin)
    before = await _metrics(client, admin_headers)

    # 10 queued + 3 processing submissions (unique (session, question) -> one question each).
    skill_id = uuid.UUID((await client.get(f"/exams/{started_exam['exam_id']}", headers=started_exam["instructor_headers"])).json()["skill_id"])
    questions = [
        Question(
            skill_id=skill_id,
            question_type=QuestionType.true_false,
            prompt=f"metrics {i}",
            difficulty=DifficultyLevel.easy,
            content={"correct_answer": True},
        )
        for i in range(13)
    ]
    db_session.add_all(questions)
    await db_session.flush()
    for i, q in enumerate(questions):
        db_session.add(
            SubmissionQueueLog(
                session_id=uuid.UUID(started_exam["session_id"]),
                question_id=q.id,
                submitted_answer="true",
                p_t_used=0.15,
                p_g_used=0.2,
                p_s_used=0.1,
                points_possible=1,
                status=SubmissionStatus.pending if i < 10 else SubmissionStatus.processing,
            )
        )
    await db_session.commit()

    # and 2 refused exam-start lock acquisitions
    user, exam = str(uuid.uuid4()), str(uuid.uuid4())
    assert await acquire_start_lock(redis_client, user, exam) is True
    assert await acquire_start_lock(redis_client, user, exam) is False
    assert await acquire_start_lock(redis_client, user, exam) is False
    await release_start_lock(redis_client, user, exam)

    after = await _metrics(client, admin_headers)
    assert after["queue_depth_queued"] - before["queue_depth_queued"] == 10
    assert after["queue_depth_processing"] - before["queue_depth_processing"] == 3
    assert after["lock_contention_last_hour"] - before["lock_contention_last_hour"] == 2
    assert after["active_websocket_connections"] == connection_manager.total_connection_count()


@pytest.mark.asyncio
async def test_metrics_are_admin_only(client, instructor, student):
    assert (await client.get("/admin/metrics")).status_code == 401
    assert (await client.get("/admin/metrics", headers=student[0])).status_code == 403
    assert (await client.get("/admin/metrics", headers=instructor[0])).status_code == 403  # admin strictly


# --- rate limiting ------------------------------------------------------------

@pytest.fixture
async def limiter_on(monkeypatch, redis_client):
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    async for key in redis_client.scan_iter("ratelimit:*"):
        await redis_client.delete(key)


@pytest.mark.asyncio
async def test_case_3_sixth_redemption_attempt_in_a_minute_is_rate_limited(client, limiter_on, student):
    headers, _ = student
    codes = [f"WRONG{i}" for i in range(6)]
    statuses = []
    for code in codes:
        res = await client.post(f"/access-codes/{code}/redeem", headers=headers)
        statuses.append(res.status_code)

    assert statuses[:5] == [404] * 5, statuses  # unknown code: a normal answer, not a limit
    assert statuses[5] == 429
    assert int(res.headers["retry-after"]) >= 1
    assert res.headers["x-request-id"]  # 429s are traceable too


@pytest.mark.asyncio
async def test_redemption_limit_is_per_user_not_shared(client, limiter_on, student, make_user):
    headers, _ = student
    for i in range(6):
        await client.post(f"/access-codes/BURN{i}/redeem", headers=headers)
    other_headers, _ = await make_user(UserRole.student)
    assert (await client.post("/access-codes/ANYTHING/redeem", headers=other_headers)).status_code == 404


@pytest.mark.asyncio
async def test_global_limit_is_per_caller_and_can_be_disabled(client, limiter_on, monkeypatch, student, make_user):
    monkeypatch.setattr(settings, "RATE_LIMIT_GLOBAL_PER_MINUTE", 3)
    headers, _ = student
    codes = [(await client.get("/skills", headers=headers)).status_code for _ in range(4)]
    assert codes == [200, 200, 200, 429]

    other_headers, _ = await make_user(UserRole.student)
    assert (await client.get("/skills", headers=other_headers)).status_code == 200  # someone else's bucket

    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", False)
    assert (await client.get("/skills", headers=headers)).status_code == 200


@pytest.mark.asyncio
async def test_rate_limiter_fails_open_when_redis_is_down(client, limiter_on, student, mocker):
    mocker.patch("app.core.rate_limit.hit", side_effect=aioredis.ConnectionError("redis down"))
    assert (await client.get("/skills", headers=student[0])).status_code == 200
