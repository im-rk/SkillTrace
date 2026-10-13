"""
Data access repository for Scheduling.
"""
from datetime import datetime
from uuid import UUID
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.scheduling.models import Exam, ExamQuestion, ExamStatus
from app.modules.live_session_gateway.models import ExamSession
from app.modules.enrollment.models import ExamEnrollment
from app.modules.question_bank.models import Question
from app.modules.quiz_engine.models import Skill


async def create_exam(session: AsyncSession, exam: Exam) -> Exam:
    session.add(exam)
    await session.commit()
    await session.refresh(exam)
    return exam


async def get_exam_by_id(session: AsyncSession, exam_id: UUID) -> Exam | None:
    result = await session.execute(select(Exam).where(Exam.id == exam_id))
    return result.scalars().first()


async def list_exams(session: AsyncSession) -> list[Exam]:
    result = await session.execute(select(Exam).order_by(Exam.start_time.desc()))
    return list(result.scalars().all())


async def list_exams_with_counts(session: AsyncSession) -> list[tuple[Exam, str, int, int]]:
    """(exam, skill name, assigned question count, enrolled student count), newest first."""
    questions = select(func.count()).select_from(ExamQuestion).where(ExamQuestion.exam_id == Exam.id).scalar_subquery()
    enrolled = select(func.count()).select_from(ExamEnrollment).where(ExamEnrollment.exam_id == Exam.id).scalar_subquery()
    result = await session.execute(
        select(Exam, Skill.name, questions, enrolled).join(Skill, Skill.id == Exam.skill_id).order_by(Exam.start_time.desc())
    )
    return [(exam, skill_name, int(q), int(e)) for exam, skill_name, q, e in result.all()]


async def has_sessions(session: AsyncSession, exam_id: UUID) -> bool:
    result = await session.execute(select(ExamSession.id).where(ExamSession.exam_id == exam_id).limit(1))
    return result.first() is not None


async def list_assigned_questions(session: AsyncSession, exam_id: UUID) -> list[tuple[ExamQuestion, Question]]:
    result = await session.execute(
        select(ExamQuestion, Question)
        .join(Question, Question.id == ExamQuestion.question_id)
        .where(ExamQuestion.exam_id == exam_id)
        .order_by(ExamQuestion.display_order)
    )
    return [(eq, q) for eq, q in result.all()]


async def assign_questions(session: AsyncSession, exam_id: UUID, exam_questions: list[ExamQuestion]) -> None:
    """Sets the exam's questions: whatever was assigned before is replaced."""
    await session.execute(delete(ExamQuestion).where(ExamQuestion.exam_id == exam_id))
    for eq in exam_questions:
        eq.exam_id = exam_id
        session.add(eq)
    await session.commit()


async def get_exam_session(session: AsyncSession, exam_id: UUID, student_id: UUID) -> ExamSession | None:
    result = await session.execute(
        select(ExamSession).where(ExamSession.exam_id == exam_id, ExamSession.student_id == student_id)
    )
    return result.scalars().first()


async def create_exam_session(session: AsyncSession, exam_id: UUID, student_id: UUID) -> ExamSession:
    exam_session = ExamSession(exam_id=exam_id, student_id=student_id)
    session.add(exam_session)
    await session.commit()
    await session.refresh(exam_session)
    return exam_session


async def get_exam_question(session: AsyncSession, exam_id: UUID, question_id: UUID) -> ExamQuestion | None:
    result = await session.execute(
        select(ExamQuestion).where(ExamQuestion.exam_id == exam_id, ExamQuestion.question_id == question_id)
    )
    return result.scalars().first()


async def list_exam_questions(session: AsyncSession, exam_id: UUID) -> list[ExamQuestion]:
    result = await session.execute(
        select(ExamQuestion).where(ExamQuestion.exam_id == exam_id).order_by(ExamQuestion.display_order)
    )
    return list(result.scalars().all())


async def close_exam(session: AsyncSession, exam: Exam) -> Exam:
    exam.status = ExamStatus.closed
    await session.commit()
    await session.refresh(exam)
    return exam


async def find_expired_open_exams(session: AsyncSession, now: datetime) -> list[Exam]:
    # No code in this codebase ever transitions Exam.status out of its
    # 'draft' default into 'scheduled'/'live' (that lifecycle isn't built
    # yet), so "not yet closed" is `!= closed` rather than an allow-list of
    # in-progress statuses -- otherwise this sweep would never match anything.
    result = await session.execute(
        select(Exam).where(Exam.status != ExamStatus.closed, Exam.end_time < now)
    )
    return list(result.scalars().all())
