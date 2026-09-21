"""
Business logic service for the Live Session Gateway.
Session creation itself lives in scheduling.service.start_exam (it needs
Phase 6's distributed lock); this module owns the connection's lifecycle
once a session already exists: heartbeats, pause/resume, and elapsed time.
"""
import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID
from fastapi import HTTPException, status
import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.modules.live_session_gateway import repository
from app.modules.live_session_gateway.websocket_manager import broadcast_exam_event
from app.modules.live_session_gateway.models import ExamSession, ExamSessionStatus, SessionEventType
from app.modules.scheduling.repository import get_exam_by_id


logger = logging.getLogger(__name__)


async def _pause(session: AsyncSession, exam_session: ExamSession, paused_at: datetime) -> None:
    await repository.set_status(session, exam_session, ExamSessionStatus.paused_disconnected)
    await repository.add_event(session, exam_session.id, SessionEventType.paused, paused_at)


async def _resume(session: AsyncSession, exam_session: ExamSession, resumed_at: datetime) -> None:
    await repository.set_status(session, exam_session, ExamSessionStatus.in_progress)
    await repository.add_event(session, exam_session.id, SessionEventType.resumed, resumed_at)


async def pause_session(session: AsyncSession, session_id: UUID, paused_at: datetime) -> None:
    # Locked and re-read: the WebSocket handler keeps ONE DB session for the whole
    # connection, so its identity map can hold a stale status. Acting on that would
    # e.g. overwrite `submitted` with `paused_disconnected` when the page reloads.
    exam_session = await repository.get_session(session, session_id, for_update=True)
    if exam_session is None or exam_session.status != ExamSessionStatus.in_progress:
        return
    await _pause(session, exam_session, paused_at)
    await session.commit()


async def resume_session(session: AsyncSession, session_id: UUID, resumed_at: datetime) -> None:
    exam_session = await repository.get_session(session, session_id, for_update=True)
    if exam_session is None or exam_session.status != ExamSessionStatus.paused_disconnected:
        return
    await _resume(session, exam_session, resumed_at)
    await session.commit()


async def update_heartbeat(session: AsyncSession, session_id: UUID) -> None:
    exam_session = await repository.get_session(session, session_id, for_update=True)
    if exam_session is None:
        return
    now = datetime.now(timezone.utc)
    if exam_session.status == ExamSessionStatus.paused_disconnected:
        # Reconnected -- resume, crediting the paused duration via the stored
        # paused/resumed events rather than mutating a running countdown.
        await _resume(session, exam_session, now)
    await repository.update_heartbeat(session, exam_session, now)
    await session.commit()


async def compute_elapsed_active_time(session: AsyncSession, session_id: UUID) -> timedelta:
    """total_duration - sum(paused_durations), derived from the discrete
    paused/resumed SessionEvent trail rather than a mutated running counter --
    robust to bugs and gives an auditable record of every disconnect."""
    exam_session = await repository.get_session(session, session_id)
    if exam_session is None:
        raise ValueError(f"No exam session {session_id}")

    events = await repository.list_events(session, session_id)
    end_reference = exam_session.completed_at or datetime.now(timezone.utc)

    total_paused = timedelta()
    pause_start: datetime | None = None
    for event in events:
        if event.event_type == SessionEventType.paused:
            pause_start = event.occurred_at
        elif event.event_type == SessionEventType.resumed and pause_start is not None:
            total_paused += event.occurred_at - pause_start
            pause_start = None
    if pause_start is not None:
        total_paused += end_reference - pause_start

    return (end_reference - exam_session.started_at) - total_paused


async def get_owned_session(session: AsyncSession, session_id: UUID, requester_id: UUID) -> ExamSession:
    """Shared 404/403 ownership guard -- used by every endpoint scoped to a
    single student's exam session (this module's own timing lookup, plus
    evaluation_pipeline's submit-answer and submission-status endpoints)."""
    exam_session = await repository.get_session(session, session_id)
    if exam_session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam session not found")
    if exam_session.student_id != requester_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your exam session")
    return exam_session


async def get_session_timing(session: AsyncSession, session_id: UUID, requester_id: UUID) -> dict:
    """Backs the frontend's periodic timer resync (Phase 11): the client
    never trusts its own tick, only this server-computed value."""
    exam_session = await get_owned_session(session, session_id, requester_id)
    exam = await get_exam_by_id(session, exam_session.exam_id)
    elapsed = await compute_elapsed_active_time(session, session_id)
    return {
        "elapsed_active_seconds": max(int(elapsed.total_seconds()), 0),
        "total_duration_seconds": exam.duration_minutes * 60,
        "status": exam_session.status.value,
    }


async def flag_stale_sessions(session: AsyncSession) -> int:
    """Periodic sweep (Celery Beat): sessions that missed ~3 heartbeats get
    paused. Reconnecting later resumes via update_heartbeat."""
    threshold = datetime.now(timezone.utc) - timedelta(seconds=settings.STALE_SESSION_THRESHOLD_SECONDS)
    stale = await repository.find_stale_sessions(session, threshold)
    now = datetime.now(timezone.utc)
    for exam_session in stale:
        await _pause(session, exam_session, now)
    await session.commit()
    return len(stale)


# --- Ending a session: manual submit, timeout auto-submit, instructor close ---

async def _finish_session(
    session: AsyncSession,
    exam_session: ExamSession,
    final_status: ExamSessionStatus,
    event_type: SessionEventType,
    now: datetime,
    duration_cap_seconds: int | None = None,
) -> None:
    # Computed before completed_at is set: the elapsed calculation treats an
    # unset completed_at as "still running until now".
    elapsed = int((await compute_elapsed_active_time(session, exam_session.id)).total_seconds())
    exam_session.total_time_used_seconds = max(min(elapsed, duration_cap_seconds) if duration_cap_seconds else elapsed, 0)
    exam_session.completed_at = now
    await repository.set_status(session, exam_session, final_status)
    await repository.add_event(session, exam_session.id, event_type, now)


async def _notify_time_up(redis_client: redis.Redis, exam_session: ExamSession) -> None:
    """Targeted at one session: sessions of the same exam end at different
    moments (per-student duration, pauses), so this must never be an
    exam-wide broadcast."""
    event = {
        "type": "time_up",
        "exam_id": str(exam_session.exam_id),
        "session_id": str(exam_session.id),
        "status": exam_session.status.value,
    }
    try:
        await broadcast_exam_event(redis_client, str(exam_session.exam_id), event)
    except Exception:  # noqa: BLE001 -- the DB state is authoritative; the client also learns via its timer resync
        logger.exception("Could not publish time_up for session %s", exam_session.id)


async def submit_exam_session(session: AsyncSession, session_id: UUID, requester_id: UUID) -> ExamSession:
    """The student finishing their exam. Idempotent: submitting an already-ended
    session just returns it."""
    await get_owned_session(session, session_id, requester_id)
    locked = await repository.get_session(session, session_id, for_update=True)
    if locked.status in repository.ACTIVE_STATUSES:
        await _finish_session(
            session, locked, ExamSessionStatus.submitted, SessionEventType.submitted, datetime.now(timezone.utc)
        )
    await session.commit()
    return locked


async def auto_submit_expired_sessions(session: AsyncSession, redis_client: redis.Redis) -> int:
    """Periodic sweep (Celery Beat). A session ends when its own active time
    (pauses excluded) reaches the exam duration, or the exam window closes."""
    now = datetime.now(timezone.utc)
    ended: list[ExamSession] = []
    for candidate, exam in await repository.find_expiry_candidates(session, now):
        window_closed = exam.end_time <= now
        if not window_closed:
            if await compute_elapsed_active_time(session, candidate.id) < timedelta(minutes=exam.duration_minutes):
                continue
        locked = await repository.get_session(session, candidate.id, for_update=True)
        if locked.status not in repository.ACTIVE_STATUSES:
            continue  # lost a race with a manual submit
        await _finish_session(
            session, locked, ExamSessionStatus.auto_submitted, SessionEventType.auto_submitted, now,
            duration_cap_seconds=exam.duration_minutes * 60,
        )
        ended.append(locked)
    await session.commit()
    for exam_session in ended:
        await _notify_time_up(redis_client, exam_session)
    return len(ended)


async def finalize_exam_sessions(session: AsyncSession, exam_id: UUID, redis_client: redis.Redis) -> int:
    """Instructor closed the exam: end every still-active session so its
    answers count towards results (mv_exam_results only includes ended sessions)."""
    now = datetime.now(timezone.utc)
    ended: list[ExamSession] = []
    for candidate in await repository.list_active_sessions_for_exam(session, exam_id):
        locked = await repository.get_session(session, candidate.id, for_update=True)
        if locked.status not in repository.ACTIVE_STATUSES:
            continue
        await _finish_session(session, locked, ExamSessionStatus.auto_submitted, SessionEventType.force_closed, now)
        ended.append(locked)
    await session.commit()
    for exam_session in ended:
        await _notify_time_up(redis_client, exam_session)
    return len(ended)
