"""
REST API routes for Enrollment.
Includes /exams/{id}/enroll, /exams/{id}/access-codes.
"""
from uuid import UUID
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.rate_limits import redeem_rate_limit
from app.core.db.session import get_db
from app.modules.iam.deps import get_current_user, require_instructor
from app.modules.iam.schemas import TokenData
from app.modules.enrollment import service
from app.modules.enrollment.schemas import (
    AccessCodeCreate,
    AccessCodeResponse,
    EnrolledStudent,
    EnrollmentResponse,
    EnrollRequest,
    MyExam,
    RedeemResult,
)

router = APIRouter(tags=["enrollment"])


@router.post("/exams/{exam_id}/enroll", response_model=EnrollmentResponse, status_code=status.HTTP_201_CREATED)
async def enroll_student(
    exam_id: UUID,
    data: EnrollRequest,
    session: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(require_instructor),
):
    return await service.enroll_student_manually(session, exam_id, data.student_id, current_user.id)


@router.get("/me/exams", response_model=list[MyExam])
async def list_my_exams(
    session: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
):
    return await service.list_my_exams(session, current_user.id)


@router.get("/exams/{exam_id}/enrollments", response_model=list[EnrolledStudent])
async def list_enrollments(
    exam_id: UUID,
    session: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(require_instructor),
):
    return await service.list_enrolled_students(session, exam_id)


@router.get("/exams/{exam_id}/access-codes", response_model=list[AccessCodeResponse])
async def list_access_codes(
    exam_id: UUID,
    session: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(require_instructor),
):
    return await service.list_access_codes(session, exam_id)


@router.post("/exams/{exam_id}/access-codes", response_model=AccessCodeResponse, status_code=status.HTTP_201_CREATED)
async def create_access_code(
    exam_id: UUID,
    data: AccessCodeCreate,
    session: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(require_instructor),
):
    return await service.generate_access_code(session, exam_id, data, current_user.id)


@router.post("/access-codes/{code}/redeem", response_model=RedeemResult, dependencies=[Depends(redeem_rate_limit)])
async def redeem_access_code(
    code: str,
    session: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
):
    return await service.redeem_access_code(session, code, current_user.id)
