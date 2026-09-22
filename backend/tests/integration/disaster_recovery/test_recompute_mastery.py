"""
student_skill_state is derived data: delete it and it must be reconstructible,
exactly, from the immutable `responses` log -- free-practice and exam answers
folded together in answered_at order.
"""
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import delete, select, text

from app.modules.evaluation_pipeline.queue_producer import submit_answer as enqueue_exam_answer
from app.modules.evaluation_pipeline.tasks import _process_submission
from app.modules.quiz_engine.mastery_recompute import list_student_skill_pairs, recompute_student_skill_state
from app.modules.quiz_engine.models import StudentSkillState

CORRECT, WRONG = "b", "a"


async def _new_question(client, headers, skill_id, difficulty) -> str:
    res = await client.post(
        "/question-bank/questions",
        json={
            "skill_id": skill_id,
            "question_type": "multiple_choice",
            "prompt": f"recovery {uuid.uuid4().hex[:6]}",
            "difficulty": difficulty,
            "content": {"choices": [{"id": "a", "text": "x"}, {"id": "b", "text": "y"}], "correct_choice_id": CORRECT},
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


async def _fresh_state(db_session, student_id, skill_id):
    """Read on a separate connection: the test's own session has an identity map."""
    async with db_session.bind.connect() as conn:
        return (
            await conn.execute(
                select(
                    StudentSkillState.current_mastery, StudentSkillState.total_attempts, StudentSkillState.is_mastered
                ).where(StudentSkillState.student_id == student_id, StudentSkillState.skill_id == skill_id)
            )
        ).first()


@pytest.fixture
async def mixed_history(client, db_session, redis_client, started_exam, skill_id):
    """Exam answers (graded by the real pipeline task), then a skill-parameter edit, then
    practice answers -- so the log holds both kinds of session AND two different sets of BKT params."""
    student_id, student_headers = uuid.UUID(started_exam["student_id"]), started_exam["student_headers"]
    instructor_headers = started_exam["instructor_headers"]

    for question_id, answer in zip(started_exam["question_ids"], (CORRECT, WRONG)):
        log = await enqueue_exam_answer(
            db_session, redis_client, uuid.UUID(started_exam["session_id"]), uuid.UUID(question_id), answer, student_id
        )
        await _process_submission(str(log.id))

    edit = await client.patch(f"/skills/{skill_id}", json={"p_t": 0.3, "p_g": 0.15, "p_s": 0.05}, headers=instructor_headers)
    assert edit.status_code == 200, edit.text

    session = (await client.post("/quiz-sessions", json={"skill_id": skill_id}, headers=student_headers)).json()
    for answer in [WRONG, CORRECT, WRONG, WRONG, CORRECT]:
        question_id = await _new_question(client, instructor_headers, skill_id, "medium")
        res = await client.post(
            f"/quiz-sessions/{session['id']}/answer",
            json={"question_id": question_id, "submitted_answer": answer},
            headers=student_headers,
        )
        assert res.status_code == 200, res.text
        assert res.json()["session_status"] == "in_progress", "history must not end in mastery for this scenario"

    return {"student_id": student_id, "skill_id": uuid.UUID(skill_id), "responses": 7}


@pytest.mark.asyncio
async def test_case_5_deleting_student_skill_state_and_recomputing_reproduces_it_exactly(db_session, mixed_history):
    student_id, skill_id = mixed_history["student_id"], mixed_history["skill_id"]
    before = await _fresh_state(db_session, student_id, skill_id)
    assert before.total_attempts == mixed_history["responses"]

    await db_session.execute(delete(StudentSkillState).where(StudentSkillState.student_id == student_id))
    await db_session.commit()
    assert await _fresh_state(db_session, student_id, skill_id) is None

    result = await recompute_student_skill_state(db_session, student_id, skill_id)

    after = await _fresh_state(db_session, student_id, skill_id)
    assert after.current_mastery == before.current_mastery, "not an exact reconstruction"  # Decimal equality, 5 dp
    assert after.total_attempts == before.total_attempts
    assert after.is_mastered == before.is_mastered
    assert result.divergences == []  # every step of the log agreed with the recomputation
    assert result.changed is True  # it really was rebuilt from nothing


@pytest.mark.asyncio
async def test_recompute_repairs_a_corrupted_row_and_is_a_no_op_when_healthy(db_session, mixed_history):
    student_id, skill_id = mixed_history["student_id"], mixed_history["skill_id"]
    healthy = await _fresh_state(db_session, student_id, skill_id)

    untouched = await recompute_student_skill_state(db_session, student_id, skill_id, apply=False)
    assert untouched.changed is False

    await db_session.execute(
        text("UPDATE student_skill_state SET current_mastery = 0.01234, total_attempts = 99 WHERE student_id = :s AND skill_id = :k"),
        {"s": student_id, "k": skill_id},
    )
    await db_session.commit()
    assert (await recompute_student_skill_state(db_session, student_id, skill_id, apply=False)).changed is True
    assert (await _fresh_state(db_session, student_id, skill_id)).current_mastery == Decimal("0.01234")  # dry run wrote nothing

    await recompute_student_skill_state(db_session, student_id, skill_id)
    repaired = await _fresh_state(db_session, student_id, skill_id)
    assert (repaired.current_mastery, repaired.total_attempts) == (healthy.current_mastery, healthy.total_attempts)


@pytest.mark.asyncio
async def test_recompute_reports_where_the_log_disagrees_with_itself(db_session, mixed_history):
    student_id, skill_id = mixed_history["student_id"], mixed_history["skill_id"]
    await db_session.execute(
        text(
            "UPDATE responses SET mastery_after = 0.99999 WHERE id = ("
            " SELECT r.id FROM responses r JOIN quiz_sessions q ON q.id = r.session_id"
            " WHERE q.student_id = :s ORDER BY r.answered_at LIMIT 1)"
        ),
        {"s": student_id},
    )
    await db_session.commit()

    result = await recompute_student_skill_state(db_session, student_id, skill_id, apply=False)
    assert any("mastery_after" in d for d in result.divergences)


@pytest.mark.asyncio
async def test_pairs_listing_covers_both_kinds_of_session_and_empty_history_is_left_alone(db_session, mixed_history, make_user, skill_id):
    from app.modules.iam.models import UserRole

    assert (mixed_history["student_id"], mixed_history["skill_id"]) in await list_student_skill_pairs(db_session)

    _, nobody = await make_user(UserRole.student)
    result = await recompute_student_skill_state(db_session, uuid.UUID(nobody), uuid.UUID(skill_id))
    assert result.mastery is None and result.total_attempts == 0
    assert await _fresh_state(db_session, uuid.UUID(nobody), uuid.UUID(skill_id)) is None
