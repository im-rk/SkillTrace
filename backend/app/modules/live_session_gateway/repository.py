"""
Data access repository for the Live Session Gateway.
"""
from datetime import datetime
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.live_session_gateway.models import ExamSession, ExamSessionStatus, SessionEvent, SessionEventType


async def get_session(session: AsyncSession, session_id: UUID) -> ExamSession | None:
    result = await session.execute(select(ExamSession).where(ExamSession.id == session_id))
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
