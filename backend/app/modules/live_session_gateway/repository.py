"""
Data access repository for the Live Session Gateway.
"""
from datetime import datetime
from uuid import UUID
from sqlalchemy import literal_column, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.live_session_gateway.models import ExamSession, ExamSessionStatus, SessionEvent, SessionEventType
from app.modules.scheduling.models import Exam

ACTIVE_STATUSES = (ExamSessionStatus.in_progress, ExamSessionStatus.paused_disconnected)


async def get_session(session: AsyncSession, session_id: UUID, for_update: bool = False) -> ExamSession | None:
    stmt = select(ExamSession).where(ExamSession.id == session_id)
    if for_update:
        # populate_existing: a row already in the identity map must reflect the
        # state we just locked, not a stale earlier read.
        stmt = stmt.with_for_update().execution_options(populate_existing=True)
    result = await session.execute(stmt)
    return result.scalars().first()


async def update_heartbeat(session: AsyncSession, exam_session: ExamSession, now: datetime) -> None:
    # No flush here: every caller commits immediately after (commit() flushes
    # implicitly), and nothing reads the row back in between -- an explicit
    # flush would just be a wasted extra round trip on every heartbeat.
    exam_session.last_heartbeat_at = now


async def set_status(session: AsyncSession, exam_session: ExamSession, status: ExamSessionStatus) -> None:
    exam_session.status = status


async def add_event(
    session: AsyncSession, session_id: UUID, event_type: SessionEventType, occurred_at: datetime
) -> SessionEvent:
    event = SessionEvent(session_id=session_id, event_type=event_type, occurred_at=occurred_at)
    session.add(event)
    return event


async def list_events(session: AsyncSession, session_id: UUID) -> list[SessionEvent]:
    result = await session.execute(
        select(SessionEvent).where(SessionEvent.session_id == session_id).order_by(SessionEvent.occurred_at)
    )
    return list(result.scalars().all())


async def find_stale_sessions(session: AsyncSession, threshold: datetime) -> list[ExamSession]:
    result = await session.execute(
        select(ExamSession).where(
            ExamSession.status == ExamSessionStatus.in_progress,
            ExamSession.last_heartbeat_at < threshold,
        )
    )
    return list(result.scalars().all())


async def find_expiry_candidates(session: AsyncSession, now: datetime) -> list[tuple[ExamSession, Exam]]:
    """Active sessions that MAY be out of time. Wall-clock time since start is
    an upper bound on active time (pauses only subtract), so any session whose
    started_at + duration is still in the future cannot have expired yet; the
    exact pause-adjusted check happens in Python for these candidates only."""
    result = await session.execute(
        select(ExamSession, Exam)
        .join(Exam, Exam.id == ExamSession.exam_id)
        .where(
            ExamSession.status.in_(ACTIVE_STATUSES),
            (Exam.end_time <= now)
            | (ExamSession.started_at + Exam.duration_minutes * literal_column("interval '1 minute'") <= now),
        )
    )
    return [(es, exam) for es, exam in result.all()]


async def list_active_sessions_for_exam(session: AsyncSession, exam_id: UUID) -> list[ExamSession]:
    result = await session.execute(
        select(ExamSession).where(ExamSession.exam_id == exam_id, ExamSession.status.in_(ACTIVE_STATUSES))
    )
    return list(result.scalars().all())
