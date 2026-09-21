"""
Business logic for the free-practice adaptive quiz.

A student's mastery of a skill is ONE chain (student_skill_state) shared by
free practice and exams: every graded answer, from either source, is a BKT
update on that row, taken under a row lock. A practice session therefore
starts from wherever the student currently is, not from p_L0.
"""
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.evaluation_pipeline.answer_evaluation import evaluate_answer
from app.modules.iam.models import UserRole
from app.modules.iam.schemas import TokenData
from app.modules.question_bank.service import strip_correct_answer
from app.modules.quiz_engine import repository
from app.modules.quiz_engine.domain.bkt.engine import update_mastery
from app.modules.quiz_engine.domain.bkt.params import BKTParams
from app.modules.quiz_engine.domain.bkt.policy import Difficulty, SessionOutcome, select_next_action
from app.modules.quiz_engine.models import QuizSession, SessionStatus, Skill
from app.modules.quiz_engine.schemas import (
    AnswerCreate,
    AnswerResponse,
    NextQuestionResponse,
    PracticeQuestion,
    ProgressPoint,
    ProgressResponse,
    QuizSessionResponse,
    SkillMastery,
    SkillReadiness,
    SkillUpdate,
    StudentMasteryRow,
)

DIFFICULTIES = ("easy", "medium", "hard")

# If the wanted tier has no unanswered question left, fall back to the nearest
# usable tier. Medium prefers *harder* (the student is past 0.4, so easy adds
# little information); easy climbs upward.
TIER_FALLBACK = {
    Difficulty.EASY: ("easy", "medium", "hard"),
    Difficulty.MEDIUM: ("medium", "hard", "easy"),
}


def _not_found(what: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{what} not found")


# --- skills -----------------------------------------------------------------

async def update_skill(session: AsyncSession, skill_id: UUID, data: SkillUpdate) -> Skill:
    skill = await repository.get_active_skill(session, skill_id)
    if skill is None:
        raise _not_found("Skill")
    for field, value in data.model_dump(exclude_unset=True, exclude_none=True).items():
        setattr(skill, field, value)
    await session.commit()
    await session.refresh(skill)
    return skill


async def delete_skill(session: AsyncSession, skill_id: UUID) -> None:
    """Soft delete: questions, exams and history keep pointing at the row."""
    skill = await repository.get_active_skill(session, skill_id)
    if skill is None:
        raise _not_found("Skill")
    skill.deleted_at = datetime.now(timezone.utc)
    await session.commit()


async def get_readiness(session: AsyncSession, skill_id: UUID) -> SkillReadiness:
    if await repository.get_active_skill(session, skill_id) is None:
        raise _not_found("Skill")
    counts = await repository.count_questions_by_difficulty(session, skill_id)
    counts = {tier: counts.get(tier, 0) for tier in DIFFICULTIES}
    missing = [tier for tier, n in counts.items() if n == 0]
    return SkillReadiness(skill_id=skill_id, counts=counts, ready=not missing, missing_tiers=missing)


async def get_skill_overview(session: AsyncSession, skill_id: UUID) -> list[StudentMasteryRow]:
    if await repository.get_active_skill(session, skill_id) is None:
        raise _not_found("Skill")
    return [
        StudentMasteryRow(
            student_id=user.id,
            display_name=user.display_name,
            email=user.email,
            current_mastery=float(state.current_mastery),
            total_attempts=state.total_attempts,
            is_mastered=state.is_mastered,
            last_updated_at=state.last_updated_at,
        )
        for state, user in await repository.list_mastery_for_skill(session, skill_id)
    ]


async def list_my_skill_mastery(session: AsyncSession, student_id: UUID) -> list[SkillMastery]:
    return [
        SkillMastery(
            skill_id=skill.id,
            name=skill.name,
            slug=skill.slug,
            description=skill.description,
            mastery_threshold=float(skill.mastery_threshold),
            question_count=question_count,
            current_mastery=float(state.current_mastery) if state else None,
            total_attempts=state.total_attempts if state else 0,
            is_mastered=state.is_mastered if state else False,
        )
        for skill, state, question_count in await repository.list_skills_with_student_state(session, student_id)
    ]


# --- practice sessions ------------------------------------------------------

def _skill_params(skill: Skill) -> BKTParams:
    return BKTParams(p_l0=float(skill.p_l0), p_t=float(skill.p_t), p_g=float(skill.p_g), p_s=float(skill.p_s))


async def _current_mastery(session: AsyncSession, quiz_session: QuizSession) -> float:
    state = await repository.get_student_skill_state(session, quiz_session.student_id, quiz_session.skill_id)
    return float(state.current_mastery) if state else float(quiz_session.initial_mastery)


async def _own_session(session: AsyncSession, quiz_session_id: UUID, student_id: UUID, for_update: bool = False) -> QuizSession:
    quiz_session = await repository.get_quiz_session(session, quiz_session_id, for_update=for_update)
    # 404 rather than 403: don't reveal that another student's session id exists.
    if quiz_session is None or quiz_session.student_id != student_id:
        raise _not_found("Quiz session")
    return quiz_session


def _require_in_progress(quiz_session: QuizSession) -> None:
    if quiz_session.status != SessionStatus.in_progress:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"This quiz session is already {quiz_session.status.value}")


def _end(quiz_session: QuizSession, new_status: SessionStatus, final_mastery: float) -> None:
    quiz_session.status = new_status
    quiz_session.final_mastery = final_mastery
    quiz_session.ended_at = datetime.now(timezone.utc)


async def _to_response(session: AsyncSession, quiz_session: QuizSession, skill: Skill) -> QuizSessionResponse:
    answered, correct = await repository.count_session_responses(session, quiz_session.id)
    return QuizSessionResponse(
        id=quiz_session.id,
        skill_id=quiz_session.skill_id,
        status=quiz_session.status.value,
        initial_mastery=float(quiz_session.initial_mastery),
        current_mastery=await _current_mastery(session, quiz_session),
        final_mastery=float(quiz_session.final_mastery) if quiz_session.final_mastery is not None else None,
        mastery_threshold=float(skill.mastery_threshold),
        questions_answered=answered,
        questions_correct=correct,
        started_at=quiz_session.started_at,
        ended_at=quiz_session.ended_at,
    )


async def start_session(session: AsyncSession, student_id: UUID, skill_id: UUID) -> QuizSessionResponse:
    skill = await repository.get_active_skill(session, skill_id)
    if skill is None:
        raise _not_found("Skill")
    if not any((await repository.count_questions_by_difficulty(session, skill_id)).values()):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This skill has no questions yet")

    await repository.lock_student_skill(session, student_id, skill_id)
    # Resume rather than pile up abandoned sessions if the student reopens the page.
    quiz_session = await repository.get_in_progress_quiz_session(session, student_id, skill_id)
    if quiz_session is None:
        state = await repository.get_student_skill_state(session, student_id, skill_id)
        initial = float(state.current_mastery) if state else float(skill.p_l0)
        quiz_session = await repository.create_quiz_session(session, student_id, skill_id, initial)
    await session.commit()
    await session.refresh(quiz_session)
    return await _to_response(session, quiz_session, skill)


async def get_session(session: AsyncSession, quiz_session_id: UUID, student_id: UUID) -> QuizSessionResponse:
    quiz_session = await _own_session(session, quiz_session_id, student_id)
    skill = await repository.get_skill(session, quiz_session.skill_id)
    return await _to_response(session, quiz_session, skill)


async def next_question(session: AsyncSession, quiz_session_id: UUID, student_id: UUID) -> NextQuestionResponse:
    quiz_session = await _own_session(session, quiz_session_id, student_id, for_update=True)
    _require_in_progress(quiz_session)
    skill = await repository.get_skill(session, quiz_session.skill_id)
    mastery = await _current_mastery(session, quiz_session)

    outcome, difficulty = select_next_action(mastery, float(skill.mastery_threshold))
    if outcome == SessionOutcome.MASTERED:
        _end(quiz_session, SessionStatus.mastered, mastery)
        await session.commit()
        return NextQuestionResponse(status="mastered", mastery=mastery, question=None)

    answered = await repository.answered_question_ids(session, quiz_session.id)
    for tier in TIER_FALLBACK[difficulty]:
        question = await repository.pick_unanswered_question(session, quiz_session.skill_id, tier, answered)
        if question is not None:
            return NextQuestionResponse(
                status="in_progress",
                mastery=mastery,
                question=PracticeQuestion(
                    id=question.id,
                    question_type=question.question_type.value,
                    prompt=question.prompt,
                    difficulty=question.difficulty.value,
                    content=strip_correct_answer(question.question_type, question.content),
                ),
            )

    # Every question in the skill has been answered this session and mastery
    # was not reached: nothing left to ask. The schema's terminal states are
    # mastered/abandoned, so this ends as abandoned; the API reports "exhausted".
    _end(quiz_session, SessionStatus.abandoned, mastery)
    await session.commit()
    return NextQuestionResponse(status="exhausted", mastery=mastery, question=None)


async def submit_answer(session: AsyncSession, quiz_session_id: UUID, student_id: UUID, data: AnswerCreate) -> AnswerResponse:
    # Lock order: quiz session, then mastery row. Serializes double-clicks on the
    # same session, and any grading (exam pipeline) touching the same mastery chain.
    quiz_session = await _own_session(session, quiz_session_id, student_id, for_update=True)
    _require_in_progress(quiz_session)
    skill = await repository.get_skill(session, quiz_session.skill_id)

    question = await repository.get_skill_question(session, quiz_session.skill_id, data.question_id)
    if question is None:
        raise _not_found("Question")
    if data.question_id in await repository.answered_question_ids(session, quiz_session.id):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This question has already been answered")

    state = await repository.get_or_create_student_skill_state(session, student_id, skill.id, float(skill.p_l0))
    is_correct = evaluate_answer(question.question_type, question.content, data.submitted_answer)
    params = _skill_params(skill)
    before = float(state.current_mastery)
    after = update_mastery(before, is_correct, params)

    await repository.create_response(
        session,
        session_id=quiz_session.id,
        question_id=question.id,
        submitted_answer=data.submitted_answer,
        is_correct=is_correct,
        mastery_before=before,
        mastery_after=after,
        p_t_used=params.p_t,
        p_g_used=params.p_g,
        p_s_used=params.p_s,
        points_awarded=Decimal("1") if is_correct else Decimal("0"),
        answered_at=datetime.now(timezone.utc),  # after both locks, so chain order == time order
    )
    is_mastered = after >= float(skill.mastery_threshold)
    await repository.update_student_skill_state(session, state, after, is_mastered)
    if is_mastered:
        _end(quiz_session, SessionStatus.mastered, after)
    await session.commit()
    return AnswerResponse(is_correct=is_correct, mastery_before=before, mastery_after=after, session_status=quiz_session.status.value)


async def quit_session(session: AsyncSession, quiz_session_id: UUID, student_id: UUID) -> QuizSessionResponse:
    quiz_session = await _own_session(session, quiz_session_id, student_id, for_update=True)
    skill = await repository.get_skill(session, quiz_session.skill_id)
    if quiz_session.status == SessionStatus.in_progress:  # quitting twice is a no-op
        _end(quiz_session, SessionStatus.abandoned, await _current_mastery(session, quiz_session))
        await session.commit()
        await session.refresh(quiz_session)
    return await _to_response(session, quiz_session, skill)


# --- progress ---------------------------------------------------------------

def require_self_or_staff(student_id: UUID, caller: TokenData) -> None:
    if caller.role == UserRole.student and caller.id != student_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only view your own progress")


async def get_progress(session: AsyncSession, student_id: UUID, skill_id: UUID) -> ProgressResponse:
    skill = await repository.get_skill(session, skill_id)
    if skill is None:
        raise _not_found("Skill")
    state = await repository.get_student_skill_state(session, student_id, skill_id)
    rows = await repository.list_progress_rows(session, student_id, skill_id)
    return ProgressResponse(
        skill_id=skill.id,
        skill_name=skill.name,
        initial_mastery=float(skill.p_l0),
        mastery_threshold=float(skill.mastery_threshold),
        current_mastery=float(state.current_mastery) if state else None,
        points=[
            ProgressPoint(
                answered_at=r.answered_at,
                mastery_before=float(r.mastery_before),
                mastery_after=float(r.mastery_after),
                is_correct=r.is_correct,
                source=r.source,
            )
            for r in rows
        ],
    )
