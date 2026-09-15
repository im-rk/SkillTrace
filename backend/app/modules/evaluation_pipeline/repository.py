"""
Data access repository for the Evaluation Pipeline's submission_queue_log.
"""
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.evaluation_pipeline.models import SubmissionQueueLog


async def get_log_entry(session: AsyncSession, log_id: UUID) -> SubmissionQueueLog | None:
    result = await session.execute(select(SubmissionQueueLog).where(SubmissionQueueLog.id == log_id))
    return result.scalars().first()
