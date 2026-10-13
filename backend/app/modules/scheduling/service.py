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
from app.core.redis_client import get_redis
from app.modules.scheduling import repository, locking
from app.modules.scheduling.models import Exam, ExamQuestion, ExamStatus
from app.modules.scheduling.schemas import (
    AssignedQuestionResponse,
    ExamCreate,
    ExamListItem,
    ExamResponse,
    AssignQuestionsRequest,
    ExamSessionResponse,
    StudentExamQuestion,
    StudentExamView,
)
from app.modules.question_bank.repository import get_by_ids as get_questions_by_ids
from app.modules.question_bank.service import strip_correct_answer
from app.modules.live_session_gateway.models import ExamSession
from app.modules.live_session_gateway.service import finalize_exam_sessions
from app.modules.enrollment.deps import check_enrollment
from app.modules.results.tasks import refresh_exam_results_task


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


async def list_exams(session: AsyncSession) -> list[ExamListItem]:
    return [
        ExamListItem(
            **ExamResponse.model_validate(exam).model_dump(exclude={"phase"}),
            skill_name=skill_name,
            question_count=question_count,
            enrolled_count=enrolled_count,
        )
        for exam, skill_name, question_count, enrolled_count in await repository.list_exams_with_counts(session)
    ]


async def list_assigned_questions(session: AsyncSession, exam_id: UUID) -> list[AssignedQuestionResponse]:
    await get_exam(session, exam_id)
    return [
        AssignedQuestionResponse(
            question_id=q.id,
            prompt=q.prompt,
            question_type=q.question_type.value,
            difficulty=q.difficulty.value,
            display_order=eq.display_order,
            points=eq.points,
        )
        for eq, q in await repository.list_assigned_questions(session, exam_id)
    ]


async def get_exam(session: AsyncSession, exam_id: UUID) -> Exam:
    exam = await repository.get_exam_by_id(session, exam_id)
    if exam is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")
    return exam


async def get_session_for_student(session: AsyncSession, exam_id: UUID, student_id: UUID) -> ExamSessionResponse:
    """Resolves a student's session_id for this exam -- e.g. so an instructor
    viewing the results overview (Phase 10, deliberately never live-joined
    against exam_sessions) can still get to that student's audit trail."""
    exam_session = await repository.get_exam_session(session, exam_id, student_id)
    if exam_session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No exam session for this student")
    return _to_session_response(exam_session)


async def assign_questions(session: AsyncSession, exam_id: UUID, data: AssignQuestionsRequest) -> None:
    exam = await repository.get_exam_by_id(session, exam_id)
    if exam is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")

    # Once a student has started, the question set is part of what they sat -- changing it would rewrite history.
    if await repository.has_sessions(session, exam_id):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Students have already started this exam, so its questions can no longer change")

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
    if exam.status == ExamStatus.closed:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This exam has been closed")
    if not (exam.start_time <= now <= exam.end_time):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Exam is not currently open (opens {exam.start_time.isoformat()}, closes {exam.end_time.isoformat()})",
        )

    # Calls enrollment's check_enrollment directly rather than depending on
    # enrollment.deps.verify_exam_access via FastAPI's Depends(): that dependency
    # resolves before this function ever runs, which would check enrollment
    # before the exam-window check above -- the wrong order per this route's
    # contract (409 for a closed window takes priority over 403 for enrollment).
    # A route serving exam content with no such ordering constraint should use
    # Depends(verify_exam_access) directly instead of this pattern.
    if not await check_enrollment(session, student_id, exam.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enrolled in this exam")

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


async def _close_exam(session: AsyncSession, exam: Exam) -> Exam:
    exam = await repository.close_exam(session, exam)
    # End every still-active session first: results only include ended sessions.
    await finalize_exam_sessions(session, exam.id, get_redis())
    refresh_exam_results_task.delay(str(exam.id))
    return exam


async def close_exam(session: AsyncSession, exam_id: UUID) -> Exam:
    exam = await repository.get_exam_by_id(session, exam_id)
    if exam is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")
    return await _close_exam(session, exam)


async def get_exam_for_student(session: AsyncSession, exam_id: UUID, student_id: UUID) -> StudentExamView:
    exam = await repository.get_exam_by_id(session, exam_id)
    if exam is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")
    if not await check_enrollment(session, student_id, exam_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enrolled in this exam")

    exam_questions = await repository.list_exam_questions(session, exam_id)
    questions_by_id = {q.id: q for q in await get_questions_by_ids(session, [eq.question_id for eq in exam_questions])}

    def _to_student_question(eq: ExamQuestion) -> StudentExamQuestion:
        q = questions_by_id[eq.question_id]
        return StudentExamQuestion(
            question_id=eq.question_id,
            prompt=q.prompt,
            question_type=q.question_type.value,
            difficulty=q.difficulty.value,
            display_order=eq.display_order,
            points=eq.points,
            content=strip_correct_answer(q.question_type, q.content),
        )

    return StudentExamView(
        exam_id=exam.id,
        title=exam.title,
        description=exam.description,
        duration_minutes=exam.duration_minutes,
        questions=[_to_student_question(eq) for eq in exam_questions],
    )


async def auto_close_expired_exams(session: AsyncSession) -> int:
    expired = await repository.find_expired_open_exams(session, datetime.now(timezone.utc))
    for exam in expired:
        await _close_exam(session, exam)
    return len(expired)
