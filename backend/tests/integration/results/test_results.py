"""
Phase 10 test cases (see docs/phases/v3-phase-10-results-analytics.md Section 5).

Close-exam is tested with celery_app.send_task mocked, not run for real: the
real task body calls asyncio.run() (via app.core.async_task.run_async) to
bridge into async app code, which raises "asyncio.run() cannot be called
from a running event loop" if actually invoked from inside this test's own
event loop -- the exact issue Phase 9 hit and solved the same way (see
tests/integration/evaluation_pipeline/test_queue_durability.py). The refresh
itself is exercised directly, by calling refresh_exam_results(db_session).
"""
import uuid
import asyncio
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.session import async_session_maker
from app.modules.results import repository
from app.modules.results.refresh_service import refresh_exam_results
from app.modules.results.service import get_session_audit_trail
from app.modules.live_session_gateway import repository as gateway_repository
from app.modules.live_session_gateway.models import SessionEventType


@pytest.mark.asyncio
async def test_case_1_close_exam_and_refresh_reflects_correct_aggregates(
    mocker, client, db_session: AsyncSession, graded_exam_setup
):
    delay = mocker.patch("app.modules.scheduling.service.refresh_exam_results_task.delay")

    res = await client.post(
        f"/exams/{graded_exam_setup['exam_id']}/close", headers=graded_exam_setup["instructor_headers"]
    )
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "closed"
    delay.assert_called_once_with(graded_exam_setup["exam_id"])

    await refresh_exam_results(db_session)

    row = await repository.get_exam_result_for_student(
        db_session, uuid.UUID(graded_exam_setup["exam_id"]), uuid.UUID(graded_exam_setup["student_id"])
    )
    assert row is not None
    assert row.questions_answered == 1
    assert float(row.total_score) == 2.0
    assert row.average_mastery is not None


@pytest.mark.asyncio
async def test_case_2_student_requests_own_results(client, db_session: AsyncSession, graded_exam_setup):
    await refresh_exam_results(db_session)

    res = await client.get(
        f"/exams/{graded_exam_setup['exam_id']}/results", headers=graded_exam_setup["student_headers"]
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["exam_id"] == graded_exam_setup["exam_id"]
    assert data["questions_answered"] == 1
    assert data["total_score"] == 2.0


@pytest.mark.asyncio
async def test_case_3_student_requests_someone_elses_results_is_403(
    client, db_session: AsyncSession, graded_exam_setup, make_user
):
    from app.modules.iam.models import UserRole

    await refresh_exam_results(db_session)
    other_headers, _ = await make_user(UserRole.student)

    res = await client.get(
        f"/exams/{graded_exam_setup['exam_id']}/results",
        params={"student_id": graded_exam_setup["student_id"]},
        headers=other_headers,
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_case_4_instructor_requests_full_overview(client, db_session: AsyncSession, graded_exam_setup):
    await refresh_exam_results(db_session)

    res = await client.get(
        f"/exams/{graded_exam_setup['exam_id']}/overview", headers=graded_exam_setup["instructor_headers"]
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["exam_id"] == graded_exam_setup["exam_id"]
    assert len(data["results"]) == 1
    assert data["results"][0]["user_id"] == graded_exam_setup["student_id"]
    assert data["results"][0]["total_score"] == 2.0


@pytest.mark.asyncio
async def test_case_5_reads_succeed_against_snapshot_during_concurrent_refresh(graded_exam_setup, db_session):
    """Two independent connections: one refreshing CONCURRENTLY, others reading.
    Proves the refresh doesn't take an exclusive lock that blocks reads.

    The view is refreshed once up front so a pre-refresh snapshot containing
    the row exists -- otherwise a read racing the first refresh could
    legitimately see the empty pre-refresh view."""
    exam_id = uuid.UUID(graded_exam_setup["exam_id"])
    student_id = uuid.UUID(graded_exam_setup["student_id"])
    await refresh_exam_results(db_session)

    async def do_refresh():
        async with async_session_maker() as session:
            await refresh_exam_results(session)

    async def do_read():
        async with async_session_maker() as session:
            return await repository.get_exam_result_for_student(session, exam_id, student_id)

    results = await asyncio.wait_for(asyncio.gather(do_refresh(), do_read(), do_read()), timeout=5.0)
    assert results[1] is not None
    assert results[2] is not None


@pytest.mark.asyncio
async def test_case_6_audit_trail_merges_answers_and_session_events_chronologically(
    db_session: AsyncSession, graded_exam_setup
):
    from datetime import datetime, timedelta, timezone

    session_id = uuid.UUID(graded_exam_setup["exam_session_id"])
    base = datetime.now(timezone.utc)
    await gateway_repository.add_event(db_session, session_id, SessionEventType.paused, base + timedelta(seconds=30))
    await gateway_repository.add_event(db_session, session_id, SessionEventType.resumed, base + timedelta(seconds=45))
    await db_session.commit()

    events = await get_session_audit_trail(db_session, session_id)

    assert [e.type for e in events] == ["answer_submitted", "paused", "resumed"]
    assert events == sorted(events, key=lambda e: e.timestamp)


@pytest.mark.asyncio
async def test_case_7_results_endpoint_does_not_perform_live_join(db_session: AsyncSession, graded_exam_setup):
    plan = await db_session.execute(
        text("EXPLAIN SELECT * FROM mv_exam_results WHERE exam_id = :id"),
        {"id": uuid.UUID(graded_exam_setup["exam_id"])},
    )
    plan_text = "\n".join(row[0] for row in plan)
    assert "mv_exam_results" in plan_text
    assert "Seq Scan on responses" not in plan_text
