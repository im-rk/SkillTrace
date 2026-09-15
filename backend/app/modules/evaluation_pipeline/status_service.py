"""
Ownership-checked submission status lookup, backing the frontend's
"submitted, being processed" vs "confirmed processed" distinction (Phase 11):
the fast-path POST only ever returns 202 Accepted, so the client polls this
to learn when the async BKT consumer (Phase 9) has actually finished.
"""
from uuid import UUID
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.evaluation_pipeline import repository
from app.modules.evaluation_pipeline.models import SubmissionQueueLog
from app.modules.live_session_gateway.service import get_owned_session


async def get_submission_status(session: AsyncSession, log_id: UUID, requester_id: UUID) -> SubmissionQueueLog:
    log_entry = await repository.get_log_entry(session, log_id)
    if log_entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found")

    # A submission belongs to whoever owns the exam session it was logged against.
    await get_owned_session(session, log_entry.session_id, requester_id)
    return log_entry
