"""
Data access repository for the Evaluation Pipeline's submission_queue_log.
"""
from uuid import UUID
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.evaluation_pipeline.models import SubmissionQueueLog, SubmissionStatus


async def get_log_entry(session: AsyncSession, log_id: UUID) -> SubmissionQueueLog | None:
    result = await session.execute(select(SubmissionQueueLog).where(SubmissionQueueLog.id == log_id))
    return result.scalars().first()


async def count_submissions_by_status(session: AsyncSession, status: SubmissionStatus) -> int:
    result = await session.execute(
        select(func.count()).select_from(SubmissionQueueLog).where(SubmissionQueueLog.status == status)
    )
    return result.scalar_one()
