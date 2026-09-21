"""
Data access repository for Quiz Engine.
"""
from datetime import datetime, timezone
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.quiz_engine.models import Response, Skill, StudentSkillState


async def get_skill(session: AsyncSession, skill_id: UUID) -> Skill | None:
    result = await session.execute(select(Skill).where(Skill.id == skill_id))
    return result.scalars().first()


async def list_skills(session: AsyncSession) -> list[Skill]:
    result = await session.execute(select(Skill).where(Skill.deleted_at.is_(None)).order_by(Skill.name))
    return list(result.scalars().all())


async def create_skill(session: AsyncSession, name: str, slug: str, description: str | None, actor_id: UUID) -> Skill:
    skill = Skill(name=name, slug=slug, description=description, created_by=actor_id)
    session.add(skill)
    await session.commit()
    await session.refresh(skill)
    return skill


async def get_student_skill_state(
    session: AsyncSession, student_id: UUID, skill_id: UUID, for_update: bool = False
) -> StudentSkillState | None:
    stmt = select(StudentSkillState).where(
        StudentSkillState.student_id == student_id, StudentSkillState.skill_id == skill_id
    )
    if for_update:
        stmt = stmt.with_for_update().execution_options(populate_existing=True)
    result = await session.execute(stmt)
    return result.scalars().first()


async def get_or_create_student_skill_state(
    session: AsyncSession, student_id: UUID, skill_id: UUID, default_mastery: float
) -> StudentSkillState:
    """Returns the student's mastery row LOCKED (FOR UPDATE) until the caller's
    transaction ends. Mastery is a chain: each update reads the previous value,
    so two concurrent gradings for the same (student, skill) -- e.g. two
    Celery workers -- would otherwise both read the same value and one update
    would be silently lost."""
    state = await get_student_skill_state(session, student_id, skill_id, for_update=True)
    if state is not None:
        return state

    # ON CONFLICT DO NOTHING rather than catch-IntegrityError-and-rollback: a
    # rollback would expire every object the caller already loaded (the
    # submission log row), and touching an expired attribute in async code
    # raises MissingGreenlet. That is exactly what happened when a student's
    # first submissions were graded concurrently.
    await session.execute(
        pg_insert(StudentSkillState)
        .values(student_id=student_id, skill_id=skill_id, current_mastery=default_mastery)
        .on_conflict_do_nothing()
    )
    return await get_student_skill_state(session, student_id, skill_id, for_update=True)


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


async def list_responses_for_exam_session(session: AsyncSession, exam_session_id: UUID) -> list[Response]:
    result = await session.execute(
        select(Response).where(Response.exam_session_id == exam_session_id).order_by(Response.answered_at)
    )
    return list(result.scalars().all())
