"""
REST API routes for Evaluation Pipeline.
Includes POST /exam-sessions/{id}/submit-answer (fast path: log + enqueue only).
"""
from uuid import UUID
from fastapi import APIRouter, Depends, status
import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.session import get_db
from app.core.redis_client import get_redis
from app.modules.iam.deps import get_current_user
from app.modules.iam.schemas import TokenData
from app.modules.evaluation_pipeline import queue_producer, status_service
from app.modules.evaluation_pipeline.schemas import (
    SubmissionAcceptedResponse,
    SubmissionPayload,
    SubmissionStatusResponse,
)

router = APIRouter(tags=["evaluation-pipeline"])


@router.post(
    "/exam-sessions/{session_id}/submit-answer",
    response_model=SubmissionAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def submit_answer(
    session_id: UUID,
    data: SubmissionPayload,
    session: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis),
    current_user: TokenData = Depends(get_current_user),
):
    log_entry = await queue_producer.submit_answer(
        session, redis_client, session_id, data.question_id, data.answer, current_user.id
    )
    return SubmissionAcceptedResponse(log_id=log_entry.id)


@router.get("/submissions/{log_id}", response_model=SubmissionStatusResponse)
async def get_submission_status(
    log_id: UUID,
    session: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
):
    log_entry = await status_service.get_submission_status(session, log_id, current_user.id)
    return SubmissionStatusResponse(log_id=log_entry.id, status=log_entry.status.value)
