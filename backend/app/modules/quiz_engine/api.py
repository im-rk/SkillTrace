"""
REST API routes for Quiz Engine: skills (catalogue + admin), the free-practice
adaptive quiz, and mastery progress.
"""
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.session import get_db
from app.modules.iam.deps import get_current_user, require_instructor
from app.modules.iam.schemas import TokenData
from app.modules.quiz_engine import repository, service
from app.modules.quiz_engine.schemas import (
    AnswerCreate,
    AnswerResponse,
    NextQuestionResponse,
    ProgressResponse,
    QuizSessionCreate,
    QuizSessionResponse,
    SkillCreate,
    SkillMastery,
    SkillReadiness,
    SkillResponse,
    SkillUpdate,
    StudentMasteryRow,
)

router = APIRouter(tags=["quiz-engine"])


# --- skills -----------------------------------------------------------------

@router.get("/skills", response_model=list[SkillResponse])
async def list_skills(
    session: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
):
    return await repository.list_skills(session)


@router.post("/skills", response_model=SkillResponse, status_code=status.HTTP_201_CREATED)
async def create_skill(
    data: SkillCreate,
    session: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(require_instructor),
):
    try:
        return await repository.create_skill(session, data.name, data.slug, data.description, current_user.id)
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A skill with this slug already exists")


@router.patch("/skills/{skill_id}", response_model=SkillResponse)
async def update_skill(
    skill_id: UUID,
    data: SkillUpdate,
    session: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(require_instructor),
):
    return await service.update_skill(session, skill_id, data)


@router.delete("/skills/{skill_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_skill(
    skill_id: UUID,
    session: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(require_instructor),
):
    await service.delete_skill(session, skill_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/skills/{skill_id}/readiness", response_model=SkillReadiness)
async def get_skill_readiness(
    skill_id: UUID,
    session: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(require_instructor),
):
    return await service.get_readiness(session, skill_id)


@router.get("/skills/{skill_id}/overview", response_model=list[StudentMasteryRow])
async def get_skill_overview(
    skill_id: UUID,
    session: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(require_instructor),
):
    return await service.get_skill_overview(session, skill_id)


# --- free-practice quiz -----------------------------------------------------

@router.post("/quiz-sessions", response_model=QuizSessionResponse, status_code=status.HTTP_201_CREATED)
async def start_quiz_session(
    data: QuizSessionCreate,
    session: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
):
    return await service.start_session(session, current_user.id, data.skill_id)


@router.get("/quiz-sessions/{quiz_session_id}", response_model=QuizSessionResponse)
async def get_quiz_session(
    quiz_session_id: UUID,
    session: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
):
    return await service.get_session(session, quiz_session_id, current_user.id)


@router.get("/quiz-sessions/{quiz_session_id}/next-question", response_model=NextQuestionResponse)
async def get_next_question(
    quiz_session_id: UUID,
    session: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
):
    return await service.next_question(session, quiz_session_id, current_user.id)


@router.post("/quiz-sessions/{quiz_session_id}/answer", response_model=AnswerResponse)
async def submit_quiz_answer(
    quiz_session_id: UUID,
    data: AnswerCreate,
    session: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
):
    return await service.submit_answer(session, quiz_session_id, current_user.id, data)


@router.post("/quiz-sessions/{quiz_session_id}/quit", response_model=QuizSessionResponse)
async def quit_quiz_session(
    quiz_session_id: UUID,
    session: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
):
    return await service.quit_session(session, quiz_session_id, current_user.id)


# --- progress ---------------------------------------------------------------

@router.get("/students/{student_id}/mastery", response_model=list[SkillMastery])
async def get_student_mastery(
    student_id: UUID,
    session: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
):
    service.require_self_or_staff(student_id, current_user)
    return await service.list_my_skill_mastery(session, student_id)


@router.get("/students/{student_id}/progress", response_model=ProgressResponse)
async def get_student_progress(
    student_id: UUID,
    skill_id: UUID,
    session: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
):
    service.require_self_or_staff(student_id, current_user)
    return await service.get_progress(session, student_id, skill_id)
