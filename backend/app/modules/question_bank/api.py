"""
REST API routes for Question Bank.
Includes POST /question-bank/bulk-import.
"""
from uuid import UUID
from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.session import get_db
from app.modules.iam.deps import get_current_user, require_instructor
from app.modules.iam.schemas import TokenData
from app.modules.question_bank import service, bulk_import_service
from app.modules.question_bank.schemas import (
    QuestionCreate,
    QuestionUpdate,
    QuestionResponse,
    BulkImportRequest,
    BulkImportResponse,
)

router = APIRouter(prefix="/question-bank", tags=["question-bank"])


@router.post("/questions", response_model=QuestionResponse, status_code=status.HTTP_201_CREATED)
async def create_question(
    data: QuestionCreate,
    session: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(require_instructor),
):
    return await service.create_question(session, data, current_user.id)


@router.get("/questions/{question_id}", response_model=QuestionResponse)
async def get_question(
    question_id: UUID,
    session: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
):
    return await service.get_question(session, question_id)


@router.get("/questions", response_model=list[QuestionResponse])
async def list_questions(
    skill_id: UUID | None = None,
    difficulty: str | None = None,
    tags: str | None = None,
    session: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
):
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else None
    return await service.list_questions(session, skill_id, difficulty, tag_list)


@router.patch("/questions/{question_id}", response_model=QuestionResponse)
async def update_question(
    question_id: UUID,
    data: QuestionUpdate,
    session: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(require_instructor),
):
    return await service.update_question(session, question_id, data, current_user.id)


@router.delete("/questions/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_question(
    question_id: UUID,
    session: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(require_instructor),
):
    await service.delete_question(session, question_id, current_user.id)


@router.post("/bulk-import", response_model=BulkImportResponse)
async def bulk_import_json(
    data: BulkImportRequest,
    session: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(require_instructor),
):
    return await bulk_import_service.bulk_import(session, data.skill_id, data.rows, current_user.id)


@router.post("/bulk-import/csv", response_model=BulkImportResponse)
async def bulk_import_csv(
    skill_id: UUID = Form(...),
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(require_instructor),
):
    raw = await file.read()
    rows = bulk_import_service.parse_csv(raw)
    return await bulk_import_service.bulk_import(session, skill_id, rows, current_user.id)
