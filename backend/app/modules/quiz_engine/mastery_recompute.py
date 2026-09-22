"""
Disaster recovery for student_skill_state.

The claim behind the schema is that `responses` is an immutable log and the
current mastery is *derived* from it. This module is the proof: fold a student's
responses for a skill -- free-practice and exam alike, in answered_at order --
through the same BKT update the live paths use, and you get the row back.

Two details make the reconstruction exact rather than approximate:
  * each step uses the p_t/p_g/p_s recorded ON THAT RESPONSE, not the skill's
    current values, so a later parameter edit doesn't change history;
  * every intermediate belief is rounded to the column's 5 decimal places,
    because the live chain stores (and re-reads) the rounded value each step.
"""
from dataclasses import dataclass, field
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.live_session_gateway.models import ExamSession
from app.modules.question_bank.models import Question
from app.modules.quiz_engine import repository
from app.modules.quiz_engine.domain.bkt.engine import update_mastery
from app.modules.quiz_engine.domain.bkt.params import BKTParams
from app.modules.quiz_engine.models import QuizSession, Response, StudentSkillState

_FIVE_DP = Decimal("0.00001")


def _round5(value: float) -> Decimal:
    # repr() round-trips the float exactly; ROUND_HALF_UP matches Postgres numeric rounding.
    return Decimal(repr(value)).quantize(_FIVE_DP, rounding=ROUND_HALF_UP)


@dataclass
class Recomputed:
    student_id: UUID
    skill_id: UUID
    mastery: Decimal | None  # None: no responses, nothing to derive
    total_attempts: int
    is_mastered: bool
    last_answered_at: datetime | None
    previous_mastery: Decimal | None  # what student_skill_state held before (None: no row)
    divergences: list[str] = field(default_factory=list)  # places the log disagrees with itself

    @property
    def changed(self) -> bool:
        return self.mastery is not None and self.mastery != self.previous_mastery


async def _responses_in_order(session: AsyncSession, student_id: UUID, skill_id: UUID) -> list[Response]:
    result = await session.execute(
        select(Response)
        .join(Question, Question.id == Response.question_id)
        .outerjoin(QuizSession, QuizSession.id == Response.session_id)
        .outerjoin(ExamSession, ExamSession.id == Response.exam_session_id)
        .where(Question.skill_id == skill_id, (QuizSession.student_id == student_id) | (ExamSession.student_id == student_id))
        .order_by(Response.answered_at, Response.id)
    )
    return list(result.scalars().all())


async def recompute_student_skill_state(
    session: AsyncSession, student_id: UUID, skill_id: UUID, apply: bool = True
) -> Recomputed:
    skill = await repository.get_skill(session, skill_id)
    if skill is None:
        raise ValueError(f"No skill {skill_id}")
    existing = await repository.get_student_skill_state(session, student_id, skill_id)
    previous = Decimal(existing.current_mastery) if existing is not None else None
    responses = await _responses_in_order(session, student_id, skill_id)
    if not responses:
        return Recomputed(student_id, skill_id, None, 0, False, None, previous)

    mastery = _round5(float(skill.p_l0))
    divergences: list[str] = []
    for index, r in enumerate(responses):
        if Decimal(r.mastery_before) != mastery:
            divergences.append(
                f"response #{index + 1} ({r.id}): recorded mastery_before {Decimal(r.mastery_before)} != recomputed {mastery}"
            )
        params = BKTParams(p_l0=float(skill.p_l0), p_t=float(r.p_t_used), p_g=float(r.p_g_used), p_s=float(r.p_s_used))
        mastery = _round5(update_mastery(float(mastery), r.is_correct, params))
        if Decimal(r.mastery_after) != mastery:
            divergences.append(
                f"response #{index + 1} ({r.id}): recorded mastery_after {Decimal(r.mastery_after)} != recomputed {mastery}"
            )

    result = Recomputed(
        student_id=student_id,
        skill_id=skill_id,
        mastery=mastery,
        total_attempts=len(responses),
        is_mastered=float(mastery) >= float(skill.mastery_threshold),
        last_answered_at=responses[-1].answered_at,
        previous_mastery=previous,
        divergences=divergences,
    )
    if apply:
        stmt = pg_insert(StudentSkillState).values(
            student_id=student_id,
            skill_id=skill_id,
            current_mastery=result.mastery,
            total_attempts=result.total_attempts,
            is_mastered=result.is_mastered,
            last_updated_at=result.last_answered_at,
        )
        await session.execute(
            stmt.on_conflict_do_update(
                index_elements=[StudentSkillState.student_id, StudentSkillState.skill_id],
                set_={
                    "current_mastery": stmt.excluded.current_mastery,
                    "total_attempts": stmt.excluded.total_attempts,
                    "is_mastered": stmt.excluded.is_mastered,
                    "last_updated_at": stmt.excluded.last_updated_at,
                },
            )
        )
        await session.commit()
    return result


async def list_student_skill_pairs(session: AsyncSession) -> list[tuple[UUID, UUID]]:
    """Every (student, skill) that has at least one response, from either kind of session."""
    practice = (
        select(QuizSession.student_id, Question.skill_id)
        .select_from(Response)
        .join(QuizSession, QuizSession.id == Response.session_id)
        .join(Question, Question.id == Response.question_id)
    )
    exam = (
        select(ExamSession.student_id, Question.skill_id)
        .select_from(Response)
        .join(ExamSession, ExamSession.id == Response.exam_session_id)
        .join(Question, Question.id == Response.question_id)
    )
    result = await session.execute(practice.union(exam))
    return [(student_id, skill_id) for student_id, skill_id in result.all()]
