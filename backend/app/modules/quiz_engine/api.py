"""
REST API routes for Quiz Engine.
GET /skills backs the skill picker in question-bank/exam admin UIs -- the
v1 free-practice adaptive quiz flow itself is not implemented.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.session import get_db
from app.modules.iam.deps import get_current_user, require_instructor
from app.modules.iam.schemas import TokenData
from app.modules.quiz_engine import repository
from app.modules.quiz_engine.schemas import SkillCreate, SkillResponse

router = APIRouter(tags=["quiz-engine"])


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
