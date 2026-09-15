"""
Celery tasks for evaluation pipeline.
Consumes stream, calls quiz_engine's BKT engine, and persists data.
"""
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from app.core.async_task import run_async
from app.core.celery_app import celery_app
from app.core.config import settings
from app.core.db.session import async_session_maker
from app.core.redis_client import get_redis
from app.modules.evaluation_pipeline import repository
from app.modules.evaluation_pipeline.answer_evaluation import evaluate_answer
from app.modules.evaluation_pipeline.models import SubmissionStatus
from app.modules.evaluation_pipeline.stream_consumer import claim_and_redeliver_pending
from app.modules.live_session_gateway import repository as session_repository
from app.modules.question_bank.repository import get_by_id as get_question_by_id
from app.modules.quiz_engine import repository as quiz_repository
from app.modules.quiz_engine.domain.bkt.engine import update_mastery
from app.modules.quiz_engine.domain.bkt.params import BKTParams


async def _process_submission(log_id: str) -> None:
    async with async_session_maker() as session:
        log_entry = await repository.get_log_entry(session, UUID(log_id))
        if log_entry is None or log_entry.status == SubmissionStatus.completed:
            # IDEMPOTENCY GUARD -- consumer groups guarantee at-least-once
            # delivery, not exactly-once. A message can be redelivered (via
            # claim_and_redeliver_pending) even after it was already fully
            # processed, if a crash happened after commit but before XACK.
            # Without this, a redelivery would double-write responses and
            # double-update student_skill_state.
            return

        log_entry.status = SubmissionStatus.processing
        await session.commit()

        exam_session = await session_repository.get_session(session, log_entry.session_id)
        question = await get_question_by_id(session, log_entry.question_id)
        skill = await quiz_repository.get_skill(session, question.skill_id)

        state = await quiz_repository.get_or_create_student_skill_state(
            session, exam_session.student_id, skill.id, float(skill.p_l0)
        )

        is_correct = evaluate_answer(question.question_type, question.content, log_entry.submitted_answer)

        # The exact same function from Phase 3, unchanged -- using the
        # p_t/p_g/p_s captured on the log row at submission time (not the
        # skill's current values), so a later parameter edit can't
        # retroactively change how an already-queued submission is scored.
        params = BKTParams(
            p_l0=float(skill.p_l0),
            p_t=float(log_entry.p_t_used),
            p_g=float(log_entry.p_g_used),
            p_s=float(log_entry.p_s_used),
        )
        new_mastery = update_mastery(float(state.current_mastery), is_correct, params)

        await quiz_repository.create_response(
            session,
            exam_session_id=exam_session.id,
            question_id=question.id,
            submitted_answer=log_entry.submitted_answer,
            is_correct=is_correct,
            mastery_before=state.current_mastery,
            mastery_after=new_mastery,
            p_t_used=log_entry.p_t_used,
            p_g_used=log_entry.p_g_used,
            p_s_used=log_entry.p_s_used,
            points_awarded=log_entry.points_possible if is_correct else Decimal("0"),
        )
        await quiz_repository.update_student_skill_state(
            session, state, new_mastery, new_mastery >= float(skill.mastery_threshold)
        )

        log_entry.status = SubmissionStatus.completed
        log_entry.processed_at = datetime.now(timezone.utc)
        await session.commit()


@celery_app.task(name="evaluation_pipeline.process_submission", bind=True, max_retries=3)
def process_submission(self, log_id: str) -> None:
    run_async(_process_submission(log_id))


@celery_app.task(name="evaluation_pipeline.sweep_pending_submissions")
def sweep_pending_submissions() -> int:
    return run_async(claim_and_redeliver_pending(get_redis(), min_idle_ms=settings.SUBMISSION_PEL_MIN_IDLE_MS))
