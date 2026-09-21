"""
Queue producer for evaluation pipeline.
Writes submission_queue_log row and pushes to Redis Stream.

No import of app.modules.quiz_engine.domain.bkt anywhere in this file --
this path only ever logs and enqueues, it never computes mastery.
"""
from uuid import UUID
from fastapi import HTTPException, status
import redis.asyncio as redis
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.evaluation_pipeline.models import SubmissionQueueLog
from app.modules.live_session_gateway.models import ExamSessionStatus
from app.modules.live_session_gateway.service import get_owned_session
from app.modules.question_bank.repository import get_by_id as get_question_by_id
from app.modules.quiz_engine import repository as quiz_repository
from app.modules.scheduling import repository as scheduling_repository

SUBMISSIONS_STREAM = "stream:submissions"


async def submit_answer(
    session: AsyncSession,
    redis_client: redis.Redis,
    exam_session_id: UUID,
    question_id: UUID,
    answer: str,
    student_id: UUID,
) -> SubmissionQueueLog:
    exam_session = await get_owned_session(session, exam_session_id, student_id)
    if exam_session.status != ExamSessionStatus.in_progress:
        # Ended sessions accept nothing. A *paused* session (connection dropped) also
        # accepts nothing: otherwise a client could stop heartbeating, freeze its own
        # exam timer, and keep answering over HTTP with unlimited time.
        detail = (
            "Exam session is paused -- reconnect to continue"
            if exam_session.status == ExamSessionStatus.paused_disconnected
            else "Exam session has ended"
        )
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)

    exam_question = await scheduling_repository.get_exam_question(session, exam_session.exam_id, question_id)
    if exam_question is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question is not part of this exam")

    question = await get_question_by_id(session, question_id)
    skill = await quiz_repository.get_skill(session, question.skill_id)

    log_entry = SubmissionQueueLog(
        session_id=exam_session_id,
        question_id=question_id,
        submitted_answer=answer,
        p_t_used=skill.p_t,
        p_g_used=skill.p_g,
        p_s_used=skill.p_s,
        points_possible=exam_question.points,
    )
    session.add(log_entry)
    # STEP 1 -- the actual durability guarantee. If the process crashes any
    # time after this line, the submission is provably not lost: it's a
    # 'pending' row waiting to be picked up, even by a recovery sweep if the
    # Redis push below never happens.
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This question was already answered")
    # No refresh() here: async_session_maker sets expire_on_commit=False, so
    # log_entry's server-generated id/defaults are already populated in memory.

    # STEP 2 -- fast, but NOT the durability guarantee. If this fails, the
    # committed row from Step 1 still exists and is recoverable.
    await redis_client.xadd(SUBMISSIONS_STREAM, {"log_id": str(log_entry.id)})

    return log_entry
