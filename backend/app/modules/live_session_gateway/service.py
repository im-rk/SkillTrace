"""
Business logic service for the Live Session Gateway.
Session creation itself lives in scheduling.service.start_exam (it needs
Phase 6's distributed lock); this module owns the connection's lifecycle
once a session already exists: heartbeats, pause/resume, and elapsed time.
"""
from datetime import datetime, timedelta, timezone
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.modules.live_session_gateway import repository
from app.modules.live_session_gateway.models import ExamSession, ExamSessionStatus, SessionEventType


async def resolve_exam_id_for_session(session: AsyncSession, session_id: UUID) -> UUID | None:
    exam_session = await repository.get_session(session, session_id)
    return exam_session.exam_id if exam_session else None


async def _pause(session: AsyncSession, exam_session: ExamSession, paused_at: datetime) -> None:
    await repository.set_status(session, exam_session, ExamSessionStatus.paused_disconnected)
    await repository.add_event(session, exam_session.id, SessionEventType.paused, paused_at)


async def _resume(session: AsyncSession, exam_session: ExamSession, resumed_at: datetime) -> None:
    await repository.set_status(session, exam_session, ExamSessionStatus.in_progress)
    await repository.add_event(session, exam_session.id, SessionEventType.resumed, resumed_at)


async def pause_session(session: AsyncSession, session_id: UUID, paused_at: datetime) -> None:
    exam_session = await repository.get_session(session, session_id)
    if exam_session is None or exam_session.status != ExamSessionStatus.in_progress:
        return
    await _pause(session, exam_session, paused_at)
    await session.commit()


async def resume_session(session: AsyncSession, session_id: UUID, resumed_at: datetime) -> None:
    exam_session = await repository.get_session(session, session_id)
    if exam_session is None or exam_session.status != ExamSessionStatus.paused_disconnected:
        return
    await _resume(session, exam_session, resumed_at)
    await session.commit()


async def update_heartbeat(session: AsyncSession, session_id: UUID) -> None:
    exam_session = await repository.get_session(session, session_id)
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
