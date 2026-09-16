"""
Business logic service for Enrollment (EnrollmentService).
Handles manual enroll, generate/redeem access codes.
"""
from datetime import datetime, timezone
from uuid import UUID
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.enrollment import repository
from app.modules.enrollment.models import ExamAccessCode, ExamEnrollment
from app.modules.enrollment.schemas import AccessCodeCreate, EnrolledStudent, RedeemResult
from app.core.audit import make_audit_entry


def _audit_entry(actor_id: UUID | None, action: str, exam_id: UUID):
    return make_audit_entry(actor_id, action, "exam_enrollment", exam_id)


async def enroll_student_manually(
    session: AsyncSession, exam_id: UUID, student_id: UUID, enrolled_by: UUID | None
) -> ExamEnrollment:
    existing = await repository.get_enrollment(session, exam_id, student_id)
    if existing is not None:
        return existing
    enrollment = await repository.create_enrollment(session, exam_id, student_id)
    session.add(_audit_entry(enrolled_by, "enroll_manual", exam_id))
    await session.commit()
    return enrollment


async def list_enrolled_students(session: AsyncSession, exam_id: UUID) -> list[EnrolledStudent]:
    rows = await repository.list_enrollments_with_students(session, exam_id)
    return [EnrolledStudent.model_validate(row, from_attributes=True) for row in rows]


async def list_access_codes(session: AsyncSession, exam_id: UUID) -> list[ExamAccessCode]:
    return await repository.list_access_codes_for_exam(session, exam_id)


async def generate_access_code(
    session: AsyncSession, exam_id: UUID, data: AccessCodeCreate, created_by: UUID | None
) -> ExamAccessCode:
    access_code = await repository.create_access_code(session, exam_id, data.max_uses, data.expires_at)
    session.add(_audit_entry(created_by, "access_code_created", exam_id))
    await session.commit()
    return access_code


async def redeem_access_code(session: AsyncSession, code: str, student_id: UUID) -> RedeemResult:
    access_code = await repository.get_access_code(session, code)
    if access_code is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid access code")

    now = datetime.now(timezone.utc)
    if access_code.expires_at is not None and access_code.expires_at < now:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Access code has expired")

    # Idempotency: a student re-redeeming the same code (double-click, refresh)
    # must not consume a second use of a max_uses-limited code.
    existing = await repository.get_enrollment(session, access_code.exam_id, student_id)
    if existing is not None:
        return RedeemResult(enrolled=True, exam_id=access_code.exam_id, access_method="access_code")

    consumed = await repository.try_increment_access_code(session, code)
    if not consumed:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Access code has reached its usage limit")

    await repository.create_enrollment(session, access_code.exam_id, student_id)
    session.add(_audit_entry(student_id, "enroll_access_code", access_code.exam_id))
    await session.commit()
    return RedeemResult(enrolled=True, exam_id=access_code.exam_id, access_method="access_code")
