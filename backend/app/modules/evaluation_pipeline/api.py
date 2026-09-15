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
from app.modules.evaluation_pipeline import queue_producer
from app.modules.evaluation_pipeline.schemas import SubmissionAcceptedResponse, SubmissionPayload

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
