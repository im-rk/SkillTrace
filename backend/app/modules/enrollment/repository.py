"""
Data access repository for Enrollment.
"""
import secrets
from datetime import datetime
from uuid import UUID
from sqlalchemy import Row, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.enrollment.models import ExamAccessCode, ExamEnrollment
from app.modules.iam.models import User
from app.modules.live_session_gateway.models import ExamSession
from app.modules.scheduling.models import Exam


async def get_enrollment(session: AsyncSession, exam_id: UUID, student_id: UUID) -> ExamEnrollment | None:
    result = await session.execute(
        select(ExamEnrollment).where(ExamEnrollment.exam_id == exam_id, ExamEnrollment.student_id == student_id)
    )
    return result.scalars().first()


async def create_enrollment(session: AsyncSession, exam_id: UUID, student_id: UUID) -> ExamEnrollment:
    enrollment = ExamEnrollment(exam_id=exam_id, student_id=student_id)
    session.add(enrollment)
    await session.flush()
    return enrollment


async def list_enrollments_with_students(session: AsyncSession, exam_id: UUID) -> list[Row]:
    """Enrollment roster for the exam-admin UI -- joins in the student's
    display_name/email since ExamEnrollment itself only has student_id."""
    result = await session.execute(
        select(ExamEnrollment.student_id, User.display_name, User.email, ExamEnrollment.enrolled_at)
        .join(User, User.id == ExamEnrollment.student_id)
        .where(ExamEnrollment.exam_id == exam_id)
        .order_by(User.display_name)
    )
    return list(result.all())


async def list_access_codes_for_exam(session: AsyncSession, exam_id: UUID) -> list[ExamAccessCode]:
    result = await session.execute(
        select(ExamAccessCode).where(ExamAccessCode.exam_id == exam_id).order_by(ExamAccessCode.created_at.desc())
    )
    return list(result.scalars().all())


def _generate_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


async def get_access_code(session: AsyncSession, code: str) -> ExamAccessCode | None:
    result = await session.execute(select(ExamAccessCode).where(ExamAccessCode.code == code))
    return result.scalars().first()


async def create_access_code(
    session: AsyncSession, exam_id: UUID, max_uses: int | None, expires_at: datetime | None
) -> ExamAccessCode:
    # Cryptographically random 6-digit code (1-in-~1e6 collision odds), not a
    # predictable sequence. `code` is the table's primary key, so a collision
    # surfaces as an IntegrityError on flush -- rely on that instead of a
    # pre-check SELECT, and retry once on the rare hit.
    for attempt in range(2):
        access_code = ExamAccessCode(
            code=_generate_code(), exam_id=exam_id, max_uses=max_uses, expires_at=expires_at
        )
        session.add(access_code)
        try:
            await session.flush()
            return access_code
        except IntegrityError:
            await session.rollback()
    raise RuntimeError("Could not generate a unique access code")


async def try_increment_access_code(session: AsyncSession, code: str) -> bool:
    """Atomically consumes one use iff the code isn't exhausted: a single guarded
    UPDATE, not a read-then-write, so two concurrent redemptions of a maxed-out
    code can't both succeed -- Postgres serializes concurrent UPDATEs on the same
    row, so only one commits before the other re-evaluates the WHERE guard."""
    result = await session.execute(
        update(ExamAccessCode)
        .where(
            ExamAccessCode.code == code,
            or_(ExamAccessCode.max_uses.is_(None), ExamAccessCode.times_used < ExamAccessCode.max_uses),
        )
        .values(times_used=ExamAccessCode.times_used + 1)
    )
    return result.rowcount == 1


async def list_exams_for_student(session: AsyncSession, student_id: UUID) -> list[Row]:
    """A student's enrolled exams, each with their own session (if they started one)."""
    result = await session.execute(
        select(
            Exam.id, Exam.title, Exam.description, Exam.status, Exam.start_time, Exam.end_time,
            Exam.duration_minutes, ExamSession.id.label("session_id"), ExamSession.status.label("session_status"),
        )
        .join(ExamEnrollment, ExamEnrollment.exam_id == Exam.id)
        .outerjoin(ExamSession, (ExamSession.exam_id == Exam.id) & (ExamSession.student_id == student_id))
        .where(ExamEnrollment.student_id == student_id)
        .order_by(Exam.start_time.desc())
    )
    return list(result.all())
