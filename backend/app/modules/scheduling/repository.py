"""
Data access repository for Scheduling.
"""
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.scheduling.models import Exam, ExamQuestion
from app.modules.live_session_gateway.models import ExamSession


async def create_exam(session: AsyncSession, exam: Exam) -> Exam:
    session.add(exam)
    await session.commit()
    await session.refresh(exam)
    return exam


async def get_exam_by_id(session: AsyncSession, exam_id: UUID) -> Exam | None:
    result = await session.execute(select(Exam).where(Exam.id == exam_id))
    return result.scalars().first()


async def assign_questions(session: AsyncSession, exam_id: UUID, exam_questions: list[ExamQuestion]) -> None:
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
