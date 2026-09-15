"""
Data access repository for Quiz Engine.
"""
from datetime import datetime, timezone
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.quiz_engine.models import Response, Skill, StudentSkillState


async def get_skill(session: AsyncSession, skill_id: UUID) -> Skill | None:
    result = await session.execute(select(Skill).where(Skill.id == skill_id))
    return result.scalars().first()


async def get_student_skill_state(
    session: AsyncSession, student_id: UUID, skill_id: UUID
) -> StudentSkillState | None:
    result = await session.execute(
        select(StudentSkillState).where(
            StudentSkillState.student_id == student_id, StudentSkillState.skill_id == skill_id
        )
    )
    return result.scalars().first()


async def get_or_create_student_skill_state(
    session: AsyncSession, student_id: UUID, skill_id: UUID, default_mastery: float
) -> StudentSkillState:
    state = await get_student_skill_state(session, student_id, skill_id)
    if state is not None:
        return state

    state = StudentSkillState(student_id=student_id, skill_id=skill_id, current_mastery=default_mastery)
    session.add(state)
    try:
        await session.flush()
    except IntegrityError:
        # Two submissions for the same (student, skill) raced to create the
        # first-ever state row; the loser just reads what the winner wrote.
        await session.rollback()
        state = await get_student_skill_state(session, student_id, skill_id)
    return state


async def update_student_skill_state(
    session: AsyncSession, state: StudentSkillState, new_mastery: float, is_mastered: bool
) -> None:
    state.current_mastery = new_mastery
    state.total_attempts += 1
    state.is_mastered = is_mastered
    state.last_updated_at = datetime.now(timezone.utc)


async def create_response(session: AsyncSession, **fields) -> Response:
    response = Response(**fields)
    session.add(response)
    return response
