"""
Business logic service for Scheduling (ExamService).
Handles creating/scheduling exams and assigning questions.
"""
import asyncio
from datetime import datetime, timezone
from uuid import UUID
from fastapi import HTTPException, status
import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.modules.scheduling import repository, locking
from app.modules.scheduling.models import Exam, ExamQuestion
from app.modules.scheduling.schemas import ExamCreate, AssignQuestionsRequest, ExamSessionResponse
from app.modules.question_bank.repository import get_by_ids as get_questions_by_ids
from app.modules.live_session_gateway.models import ExamSession


async def create_exam(session: AsyncSession, data: ExamCreate, actor_id: UUID) -> Exam:
    exam = Exam(
        title=data.title,
        description=data.description,
        skill_id=data.skill_id,
        start_time=data.start_time,
        end_time=data.end_time,
        duration_minutes=data.duration_minutes,
        created_by=actor_id,
    )
    return await repository.create_exam(session, exam)


async def assign_questions(session: AsyncSession, exam_id: UUID, data: AssignQuestionsRequest) -> None:
    exam = await repository.get_exam_by_id(session, exam_id)
    if exam is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")

    question_ids = [item.question_id for item in data.questions]
    questions_by_id = {q.id: q for q in await get_questions_by_ids(session, question_ids)}
    missing = [str(qid) for qid in question_ids if qid not in questions_by_id]
    if missing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Question(s) not found: {missing}")

    # Snapshot each question's current version so later edits don't retroactively
    # change what the student was actually shown during this exam.
    exam_questions = [
        ExamQuestion(
            question_id=item.question_id,
            question_version=questions_by_id[item.question_id].version,
            display_order=item.display_order,
            points=item.points,
        )
        for item in data.questions
    ]
    await repository.assign_questions(session, exam_id, exam_questions)


async def verify_exam_access(session: AsyncSession, exam: Exam, student_id: UUID) -> None:
    """ponytail: TODO(Phase 7) — replace with the real enrollment check
    (Enrollment.verify_exam_access). No-op for now: any authenticated student
    can start any exam. Named and called explicitly, rather than skipped
    silently, so Phase 7 has a single obvious seam to wire into."""
    return None


def _to_session_response(exam_session: ExamSession) -> ExamSessionResponse:
    return ExamSessionResponse(
        session_id=exam_session.id,
        exam_id=exam_session.exam_id,
        status=exam_session.status.value,
        started_at=exam_session.started_at,
    )


async def _poll_for_session(
    session: AsyncSession, exam_id: UUID, student_id: UUID, timeout_ms: int = 2000, interval_ms: int = 100
) -> ExamSession | None:
    elapsed_ms = 0
    while elapsed_ms < timeout_ms:
        existing = await repository.get_exam_session(session, exam_id, student_id)
        if existing is not None:
            return existing
        await asyncio.sleep(interval_ms / 1000)
        elapsed_ms += interval_ms
    return await repository.get_exam_session(session, exam_id, student_id)


async def start_exam(
    session: AsyncSession, redis_client: redis.Redis, exam_id: UUID, student_id: UUID
) -> ExamSessionResponse:
    exam = await repository.get_exam_by_id(session, exam_id)
    if exam is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")

    now = datetime.now(timezone.utc)
    if not (exam.start_time <= now <= exam.end_time):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Exam is not currently open (opens {exam.start_time.isoformat()}, closes {exam.end_time.isoformat()})",
        )

    await verify_exam_access(session, exam, student_id)

    lock_acquired = await locking.acquire_start_lock(
        redis_client, str(student_id), str(exam_id), ttl_ms=settings.EXAM_START_LOCK_TTL_MS
    )
    if not lock_acquired:
        existing = await _poll_for_session(session, exam_id, student_id)
        if existing is not None:
            return _to_session_response(existing)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Exam start already in progress, please retry")

    try:
        # Existence check MUST happen inside the lock's critical section — checking
        # before acquiring the lock would let two concurrent requests both see "no
        # session" and both create one, which is the exact race the lock prevents.
        existing = await repository.get_exam_session(session, exam_id, student_id)
        if existing is not None:
            return _to_session_response(existing)
        exam_session = await repository.create_exam_session(session, exam_id, student_id)
        return _to_session_response(exam_session)
    finally:
        await locking.release_start_lock(redis_client, str(student_id), str(exam_id))
