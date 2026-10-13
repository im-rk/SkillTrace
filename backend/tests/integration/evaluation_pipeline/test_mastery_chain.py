"""
BKT mastery is a chain: every update reads the previous value. If two graders
process the same student's answers at the same moment and neither holds a lock,
they read the same "previous" value and one update is silently lost -- the
final mastery no longer equals the fold of that student's responses.
"""
import asyncio
import uuid

import pytest
from sqlalchemy import select

from app.modules.evaluation_pipeline.queue_producer import submit_answer
from app.modules.evaluation_pipeline.tasks import _process_submission
from app.modules.quiz_engine.domain.bkt.engine import update_mastery
from app.modules.quiz_engine.domain.bkt.params import BKTParams
from app.modules.quiz_engine.models import Response, StudentSkillState
from app.modules.scheduling.models import ExamQuestion


@pytest.mark.asyncio
async def test_concurrent_grading_keeps_the_mastery_chain_intact(client, db_session, redis_client, started_exam):
    # Six more questions so eight answers can be graded in parallel.
    extra = []
    for i in range(6):
        res = await client.post(
            "/question-bank/questions",
            json={
                "skill_id": (await client.get(f"/exams/{started_exam['exam_id']}", headers=started_exam["instructor_headers"])).json()["skill_id"],
                "question_type": "multiple_choice",
                "prompt": f"Extra {i}",
                "difficulty": "easy",
                "content": {"choices": [{"id": "a", "text": "x"}, {"id": "b", "text": "y"}], "correct_choice_id": "b"},
            },
            headers=started_exam["instructor_headers"],
        )
        extra.append(res.json()["id"])
    # Setup, not under test: put the extra questions on the (already started) exam directly. The API deliberately
    # refuses to change an exam's questions once a student has started.
    for i, question_id in enumerate(extra):
        db_session.add(ExamQuestion(exam_id=uuid.UUID(started_exam["exam_id"]), question_id=uuid.UUID(question_id), question_version=1, display_order=10 + i, points=1))
    await db_session.commit()

    question_ids = started_exam["question_ids"] + extra
    # Alternate right/wrong: correct and incorrect updates do not commute, so any
    # lost or reordered update changes the final value.
    answers = ["b" if i % 2 == 0 else "a" for i in range(len(question_ids))]
    logs = [
        await submit_answer(
            db_session, redis_client, uuid.UUID(started_exam["session_id"]), uuid.UUID(q), a, uuid.UUID(started_exam["student_id"])
        )
        for q, a in zip(question_ids, answers)
    ]

    await asyncio.gather(*[_process_submission(str(log.id)) for log in logs])

    async with db_session.bind.connect() as conn:  # fresh read, not the test's identity map
        rows = (
            await conn.execute(
                select(Response.mastery_before, Response.mastery_after, Response.is_correct, Response.p_t_used, Response.p_g_used, Response.p_s_used)
                .where(Response.exam_session_id == uuid.UUID(started_exam["session_id"]))
                .order_by(Response.answered_at)
            )
        ).all()
        state = (
            await conn.execute(
                select(StudentSkillState.current_mastery, StudentSkillState.total_attempts).where(
                    StudentSkillState.student_id == uuid.UUID(started_exam["student_id"])
                )
            )
        ).one()

    assert len(rows) == len(question_ids)
    assert state.total_attempts == len(question_ids), "an update was lost"

    expected = 0.3  # skill default P(L0)
    for row in rows:
        assert float(row.mastery_before) == pytest.approx(expected, abs=1e-4), "chain broken: stale read"
        params = BKTParams(p_l0=0.3, p_t=float(row.p_t_used), p_g=float(row.p_g_used), p_s=float(row.p_s_used))
        expected = update_mastery(float(row.mastery_before), row.is_correct, params)
        assert float(row.mastery_after) == pytest.approx(expected, abs=1e-4)
    assert float(state.current_mastery) == pytest.approx(expected, abs=1e-4)
