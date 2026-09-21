"""
Ending an exam: manual submit, timeout auto-submit (with a targeted time_up
push), instructor close finalizing live sessions, and rejecting answers to
sessions that can no longer accept them.
"""
import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis_client import get_redis
from app.modules.live_session_gateway import repository as gateway_repository
from app.modules.live_session_gateway import service as gateway_service
from app.modules.live_session_gateway.models import ExamSession, ExamSessionStatus, SessionEventType
from app.modules.scheduling.models import Exam
from tests.integration.conftest import create_exam, enroll_student


async def _answer(client, started_exam, question_index=0, answer="b"):
    return await client.post(
        f"/exam-sessions/{started_exam['session_id']}/submit-answer",
        json={"question_id": started_exam["question_ids"][question_index], "answer": answer},
        headers=started_exam["student_headers"],
    )


async def _set_started_at(db_session: AsyncSession, session_id: str, started_at: datetime) -> None:
    await db_session.execute(update(ExamSession).where(ExamSession.id == uuid.UUID(session_id)).values(started_at=started_at))
    await db_session.commit()


async def _reload_session(db_session: AsyncSession, session_id: str) -> ExamSession:
    session = await gateway_repository.get_session(db_session, uuid.UUID(session_id))
    await db_session.refresh(session)
    return session


@pytest.mark.asyncio
async def test_student_submits_exam_and_it_becomes_final(client, db_session, started_exam):
    res = await client.post(f"/exam-sessions/{started_exam['session_id']}/submit", headers=started_exam["student_headers"])
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "submitted"
    assert res.json()["completed_at"] is not None

    events = await gateway_repository.list_events(db_session, uuid.UUID(started_exam["session_id"]))
    assert [e.event_type for e in events] == [SessionEventType.submitted]

    # Idempotent: a second submit returns the same final state, no second event.
    again = await client.post(f"/exam-sessions/{started_exam['session_id']}/submit", headers=started_exam["student_headers"])
    assert again.status_code == 200 and again.json()["status"] == "submitted"
    assert len(await gateway_repository.list_events(db_session, uuid.UUID(started_exam["session_id"]))) == 1

    # ...and answers are no longer accepted.
    late = await _answer(client, started_exam)
    assert late.status_code == 409
    assert "ended" in late.json()["detail"]


@pytest.mark.asyncio
async def test_submitting_someone_elses_session_is_403(client, started_exam, make_user):
    from app.modules.iam.models import UserRole

    other_headers, _ = await make_user(UserRole.student)
    res = await client.post(f"/exam-sessions/{started_exam['session_id']}/submit", headers=other_headers)
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_answering_the_same_question_twice_is_rejected(client, started_exam):
    first = await _answer(client, started_exam, 0)
    assert first.status_code == 202
    second = await _answer(client, started_exam, 0)
    assert second.status_code == 409
    assert "already answered" in second.json()["detail"]
    # A different question is still fine.
    assert (await _answer(client, started_exam, 1)).status_code == 202


@pytest.mark.asyncio
async def test_paused_session_cannot_answer_until_it_reconnects(client, db_session, started_exam):
    await gateway_service.pause_session(db_session, uuid.UUID(started_exam["session_id"]), datetime.now(timezone.utc))
    res = await _answer(client, started_exam)
    assert res.status_code == 409
    assert "paused" in res.json()["detail"]

    await gateway_service.update_heartbeat(db_session, uuid.UUID(started_exam["session_id"]))  # reconnect
    assert (await _answer(client, started_exam)).status_code == 202


@pytest.mark.asyncio
async def test_sweep_auto_submits_only_sessions_out_of_time(db_session, started_exam):
    now = datetime.now(timezone.utc)

    # Within the 60-minute duration: untouched.
    assert await gateway_service.auto_submit_expired_sessions(db_session, get_redis()) == 0

    # Started 2 hours ago (duration is 60 minutes) with no pauses: out of time.
    await _set_started_at(db_session, started_exam["session_id"], now - timedelta(hours=2))
    assert await gateway_service.auto_submit_expired_sessions(db_session, get_redis()) == 1

    ended = await _reload_session(db_session, started_exam["session_id"])
    assert ended.status == ExamSessionStatus.auto_submitted
    assert ended.completed_at is not None
    assert ended.total_time_used_seconds == 60 * 60  # capped at the exam duration
    events = await gateway_repository.list_events(db_session, ended.id)
    assert events[-1].event_type == SessionEventType.auto_submitted

    # Running the sweep again finds nothing new.
    assert await gateway_service.auto_submit_expired_sessions(db_session, get_redis()) == 0


@pytest.mark.asyncio
async def test_time_spent_disconnected_does_not_count_against_the_student(db_session, started_exam):
    session_id = uuid.UUID(started_exam["session_id"])
    now = datetime.now(timezone.utc)
    # Started 70 min ago, but was disconnected for 20 of them: 50 active minutes < 60.
    await _set_started_at(db_session, started_exam["session_id"], now - timedelta(minutes=70))
    await gateway_repository.add_event(db_session, session_id, SessionEventType.paused, now - timedelta(minutes=50))
    await gateway_repository.add_event(db_session, session_id, SessionEventType.resumed, now - timedelta(minutes=30))
    await db_session.commit()

    assert await gateway_service.auto_submit_expired_sessions(db_session, get_redis()) == 0
    assert (await _reload_session(db_session, started_exam["session_id"])).status == ExamSessionStatus.in_progress


@pytest.mark.asyncio
async def test_sweep_ends_sessions_when_the_exam_window_closes(db_session, started_exam):
    await db_session.execute(
        update(Exam)
        .where(Exam.id == uuid.UUID(started_exam["exam_id"]))
        .values(end_time=datetime.now(timezone.utc) - timedelta(seconds=1))
    )
    await db_session.commit()
    assert await gateway_service.auto_submit_expired_sessions(db_session, get_redis()) == 1


@pytest.mark.asyncio
async def test_time_up_is_pushed_to_that_session_only(db_session, started_exam):
    redis_client = get_redis()
    pubsub = redis_client.pubsub()
    await pubsub.subscribe(f"exam_events:{started_exam['exam_id']}")
    await pubsub.get_message(timeout=1)  # subscription confirmation

    await _set_started_at(db_session, started_exam["session_id"], datetime.now(timezone.utc) - timedelta(hours=2))
    await gateway_service.auto_submit_expired_sessions(db_session, redis_client)

    message = None
    for _ in range(20):
        message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=0.5)
        if message:
            break
    await pubsub.aclose()
    assert message is not None, "time_up was never published"
    event = json.loads(message["data"])
    assert event["type"] == "time_up"
    assert event["session_id"] == started_exam["session_id"]  # targeted, not an exam-wide broadcast
    assert event["status"] == "auto_submitted"


@pytest.mark.asyncio
async def test_closing_an_exam_ends_live_sessions(client, mocker, db_session, started_exam):
    mocker.patch("app.modules.scheduling.service.refresh_exam_results_task.delay")
    res = await client.post(f"/exams/{started_exam['exam_id']}/close", headers=started_exam["instructor_headers"])
    assert res.status_code == 200

    session = await _reload_session(db_session, started_exam["session_id"])
    assert session.status == ExamSessionStatus.auto_submitted
    events = await gateway_repository.list_events(db_session, session.id)
    assert events[-1].event_type == SessionEventType.force_closed

    assert (await _answer(client, started_exam)).status_code == 409


@pytest.mark.asyncio
async def test_cannot_start_a_closed_exam(client, mocker, instructor, student, skill_id):
    mocker.patch("app.modules.scheduling.service.refresh_exam_results_task.delay")
    instructor_headers, _ = instructor
    student_headers, student_id = student
    exam_id = await create_exam(client, instructor_headers, skill_id)
    await enroll_student(client, instructor_headers, exam_id, student_id)
    await client.post(f"/exams/{exam_id}/close", headers=instructor_headers)

    res = await client.post(f"/exams/{exam_id}/start", headers=student_headers)
    assert res.status_code == 409
    assert "closed" in res.json()["detail"]


@pytest.mark.asyncio
async def test_exam_phase_is_derived_from_the_clock(client, instructor, skill_id):
    instructor_headers, _ = instructor
    live = await create_exam(client, instructor_headers, skill_id)
    upcoming = await create_exam(client, instructor_headers, skill_id, start_offset=timedelta(hours=1), end_offset=timedelta(hours=2))
    ended = await create_exam(client, instructor_headers, skill_id, start_offset=timedelta(hours=-2), end_offset=timedelta(hours=-1))

    phases = {}
    for label, exam_id in (("live", live), ("upcoming", upcoming), ("ended", ended)):
        phases[label] = (await client.get(f"/exams/{exam_id}", headers=instructor_headers)).json()["phase"]
    assert phases == {"live": "live", "upcoming": "upcoming", "ended": "ended"}


@pytest.mark.asyncio
async def test_my_exams_lists_enrolled_exams_with_session_state(client, started_exam):
    res = await client.get("/me/exams", headers=started_exam["student_headers"])
    assert res.status_code == 200
    rows = res.json()
    assert len(rows) == 1
    assert rows[0]["exam_id"] == started_exam["exam_id"]
    assert rows[0]["phase"] == "live"
    assert rows[0]["session_id"] == started_exam["session_id"]
    assert rows[0]["session_status"] == "in_progress"

    await client.post(f"/exam-sessions/{started_exam['session_id']}/submit", headers=started_exam["student_headers"])
    rows = (await client.get("/me/exams", headers=started_exam["student_headers"])).json()
    assert rows[0]["session_status"] == "submitted"
