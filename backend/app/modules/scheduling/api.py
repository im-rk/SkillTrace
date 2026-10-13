"""
REST API routes for Scheduling.
Includes /exams, /exams/{id}/start.
"""
from uuid import UUID
from fastapi import APIRouter, Depends, status
import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.session import get_db
from app.core.redis_client import get_redis
from app.modules.iam.deps import get_current_user, require_instructor
from app.modules.iam.schemas import TokenData
from app.modules.scheduling import service
from app.modules.scheduling.schemas import (
    ExamCreate,
    ExamResponse,
    ExamListItem,
    AssignedQuestionResponse,
    AssignQuestionsRequest,
    ExamSessionResponse,
    StudentExamView,
)

router = APIRouter(prefix="/exams", tags=["scheduling"])


@router.post("", response_model=ExamResponse, status_code=status.HTTP_201_CREATED)
async def create_exam(
    data: ExamCreate,
    session: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(require_instructor),
):
    return await service.create_exam(session, data, current_user.id)


@router.get("", response_model=list[ExamListItem])
async def list_exams(
    session: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(require_instructor),
):
    return await service.list_exams(session)


@router.get("/{exam_id}", response_model=ExamResponse)
async def get_exam(
    exam_id: UUID,
    session: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(require_instructor),
):
    return await service.get_exam(session, exam_id)


@router.get("/{exam_id}/assigned-questions", response_model=list[AssignedQuestionResponse])
async def list_assigned_questions(
    exam_id: UUID,
    session: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(require_instructor),
):
    return await service.list_assigned_questions(session, exam_id)


@router.get("/{exam_id}/students/{student_id}/session", response_model=ExamSessionResponse)
async def get_session_for_student(
    exam_id: UUID,
    student_id: UUID,
    session: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(require_instructor),
):
    return await service.get_session_for_student(session, exam_id, student_id)


@router.post("/{exam_id}/questions", status_code=status.HTTP_204_NO_CONTENT)
async def assign_questions(
    exam_id: UUID,
    data: AssignQuestionsRequest,
    session: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(require_instructor),
):
    await service.assign_questions(session, exam_id, data)


@router.post("/{exam_id}/close", response_model=ExamResponse)
async def close_exam(
    exam_id: UUID,
    session: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(require_instructor),
):
    return await service.close_exam(session, exam_id)


@router.get("/{exam_id}/questions", response_model=StudentExamView)
async def get_exam_for_student(
    exam_id: UUID,
    session: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
):
    return await service.get_exam_for_student(session, exam_id, current_user.id)


@router.post("/{exam_id}/start", response_model=ExamSessionResponse)
async def start_exam(
    exam_id: UUID,
    session: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis),
    current_user: TokenData = Depends(get_current_user),
):
    return await service.start_exam(session, redis_client, exam_id, current_user.id)
