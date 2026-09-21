"""
Data access repository for Quiz Engine.
"""
from datetime import datetime, timezone
from uuid import UUID
from sqlalchemy import case, func, literal, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.iam.models import User
from app.modules.live_session_gateway.models import ExamSession
from app.modules.question_bank.models import Question
from app.modules.quiz_engine.models import QuizSession, Response, Skill, StudentSkillState


async def get_skill(session: AsyncSession, skill_id: UUID) -> Skill | None:
    result = await session.execute(select(Skill).where(Skill.id == skill_id))
    return result.scalars().first()


async def get_active_skill(session: AsyncSession, skill_id: UUID) -> Skill | None:
    result = await session.execute(select(Skill).where(Skill.id == skill_id, Skill.deleted_at.is_(None)))
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


# --- skill administration ---------------------------------------------------

async def count_questions_by_difficulty(session: AsyncSession, skill_id: UUID) -> dict[str, int]:
    result = await session.execute(
        select(Question.difficulty, func.count())
        .where(Question.skill_id == skill_id, Question.deleted_at.is_(None))
        .group_by(Question.difficulty)
    )
    return {difficulty.value: count for difficulty, count in result.all()}


async def list_mastery_for_skill(session: AsyncSession, skill_id: UUID) -> list[tuple[StudentSkillState, User]]:
    result = await session.execute(
        select(StudentSkillState, User)
        .join(User, User.id == StudentSkillState.student_id)
        .where(StudentSkillState.skill_id == skill_id)
        .order_by(StudentSkillState.current_mastery.desc(), User.display_name)
    )
    return [(state, user) for state, user in result.all()]


async def list_skills_with_student_state(session: AsyncSession, student_id: UUID):
    """Every active skill with the student's state (if any) and its live question count."""
    question_count = (
        select(func.count())
        .select_from(Question)
        .where(Question.skill_id == Skill.id, Question.deleted_at.is_(None))
        .scalar_subquery()
    )
    result = await session.execute(
        select(Skill, StudentSkillState, question_count)
        .outerjoin(
            StudentSkillState,
            (StudentSkillState.skill_id == Skill.id) & (StudentSkillState.student_id == student_id),
        )
        .where(Skill.deleted_at.is_(None))
        .order_by(Skill.name)
    )
    return result.all()


# --- free-practice quiz sessions --------------------------------------------

async def lock_student_skill(session: AsyncSession, student_id: UUID, skill_id: UUID) -> None:
    """Transaction-scoped advisory lock so two concurrent 'start practice' calls
    for the same (student, skill) can't both create an in-progress session."""
    await session.execute(
        select(func.pg_advisory_xact_lock(func.hashtextextended(literal(f"quiz-start:{student_id}:{skill_id}"), 0)))
    )


async def get_quiz_session(session: AsyncSession, quiz_session_id: UUID, for_update: bool = False) -> QuizSession | None:
    stmt = select(QuizSession).where(QuizSession.id == quiz_session_id)
    if for_update:
        stmt = stmt.with_for_update().execution_options(populate_existing=True)
    result = await session.execute(stmt)
    return result.scalars().first()


async def get_in_progress_quiz_session(session: AsyncSession, student_id: UUID, skill_id: UUID) -> QuizSession | None:
    result = await session.execute(
        select(QuizSession)
        .where(QuizSession.student_id == student_id, QuizSession.skill_id == skill_id, QuizSession.status == "in_progress")
        .order_by(QuizSession.started_at.desc())
    )
    return result.scalars().first()


async def create_quiz_session(session: AsyncSession, student_id: UUID, skill_id: UUID, initial_mastery: float) -> QuizSession:
    quiz_session = QuizSession(student_id=student_id, skill_id=skill_id, initial_mastery=initial_mastery)
    session.add(quiz_session)
    await session.flush()
    return quiz_session


async def answered_question_ids(session: AsyncSession, quiz_session_id: UUID) -> set[UUID]:
    result = await session.execute(select(Response.question_id).where(Response.session_id == quiz_session_id))
    return set(result.scalars().all())


async def count_session_responses(session: AsyncSession, quiz_session_id: UUID) -> tuple[int, int]:
    """(answered, correct)"""
    result = await session.execute(
        select(func.count(), func.coalesce(func.sum(case((Response.is_correct, 1), else_=0)), 0)).where(
            Response.session_id == quiz_session_id
        )
    )
    answered, correct = result.one()
    return answered, int(correct)


async def pick_unanswered_question(
    session: AsyncSession, skill_id: UUID, difficulty: str, answered_ids: set[UUID]
) -> Question | None:
    stmt = select(Question).where(
        Question.skill_id == skill_id, Question.difficulty == difficulty, Question.deleted_at.is_(None)
    )
    if answered_ids:
        stmt = stmt.where(Question.id.not_in(answered_ids))
    result = await session.execute(stmt.order_by(func.random()).limit(1))
    return result.scalars().first()


async def get_skill_question(session: AsyncSession, skill_id: UUID, question_id: UUID) -> Question | None:
    result = await session.execute(
        select(Question).where(Question.id == question_id, Question.skill_id == skill_id, Question.deleted_at.is_(None))
    )
    return result.scalars().first()


# --- progress ---------------------------------------------------------------

async def list_progress_rows(session: AsyncSession, student_id: UUID, skill_id: UUID):
    """Every graded response by this student on this skill, free practice and
    exam alike (the schema's exactly-one-of session_id / exam_session_id split),
    oldest first, tagged with where it came from."""
    result = await session.execute(
        select(
            Response.answered_at,
            Response.mastery_before,
            Response.mastery_after,
            Response.is_correct,
            case((Response.session_id.is_not(None), "practice"), else_="exam").label("source"),
        )
        .join(Question, Question.id == Response.question_id)
        .outerjoin(QuizSession, QuizSession.id == Response.session_id)
        .outerjoin(ExamSession, ExamSession.id == Response.exam_session_id)
        .where(
            Question.skill_id == skill_id,
            func.coalesce(QuizSession.student_id, ExamSession.student_id) == student_id,
        )
        .order_by(Response.answered_at, Response.id)
    )
    return result.all()
