"""
Data access repository for Scheduling.
"""
from datetime import datetime
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.scheduling.models import Exam, ExamQuestion, ExamStatus
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
