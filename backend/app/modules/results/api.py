"""
REST API routes for Results.
"""
from uuid import UUID
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.session import get_db
from app.modules.iam.deps import get_current_user, require_instructor
from app.modules.iam.schemas import TokenData
from app.modules.results import service
from app.modules.results.schemas import AuditTrailResponse, ExamOverviewResponse, StudentExamResult

router = APIRouter(tags=["results"])


@router.get("/exams/{exam_id}/results", response_model=StudentExamResult)
async def get_exam_results(
    exam_id: UUID,
    student_id: UUID | None = None,
    session: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
):
    return await service.get_exam_result(session, exam_id, current_user.id, current_user.role, student_id)


@router.get("/exams/{exam_id}/overview", response_model=ExamOverviewResponse)
async def get_exam_overview(
    exam_id: UUID,
    session: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(require_instructor),
):
    return await service.get_exam_overview(session, exam_id)


@router.get("/exam-sessions/{session_id}/audit-trail", response_model=AuditTrailResponse)
async def get_audit_trail(
    session_id: UUID,
    session: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(require_instructor),
):
    events = await service.get_session_audit_trail(session, session_id)
    return AuditTrailResponse(session_id=session_id, events=events)
