import uuid
from datetime import datetime, timezone
import pytest
from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.evaluation_pipeline.queue_producer import submit_answer
from app.modules.evaluation_pipeline.tasks import _process_submission
from app.modules.live_session_gateway.models import ExamSession, ExamSessionStatus
from tests.integration.conftest import create_exam, enroll_student


@pytest.fixture
async def graded_exam_setup(
    client: AsyncClient, db_session: AsyncSession, redis_client, instructor, student, skill_id
):
    """An enrolled student with a closed-out exam session: one correctly
    answered MCQ question already processed into a `responses` row, and the
    exam_session itself marked 'submitted' so it is eligible for
    mv_exam_results (per the view's WHERE clause)."""
    instructor_headers, instructor_id = instructor
    student_headers, student_id = student

    exam_id = await create_exam(client, instructor_headers, skill_id)
    await enroll_student(client, instructor_headers, exam_id, student_id)

    question_payload = {
        "skill_id": skill_id,
        "question_type": "multiple_choice",
        "prompt": "What is 2 + 2?",
        "difficulty": "easy",
        "content": {"choices": [{"id": "a", "text": "3"}, {"id": "b", "text": "4"}], "correct_choice_id": "b"},
    }
    q_res = await client.post("/question-bank/questions", json=question_payload, headers=instructor_headers)
    assert q_res.status_code == 201, q_res.text
    question_id = q_res.json()["id"]

    assign_res = await client.post(
        f"/exams/{exam_id}/questions",
        json={"questions": [{"question_id": question_id, "display_order": 1, "points": "2.0"}]},
        headers=instructor_headers,
    )
    assert assign_res.status_code == 204, assign_res.text

    start_res = await client.post(f"/exams/{exam_id}/start", headers=student_headers)
    assert start_res.status_code == 200, start_res.text
    exam_session_id = start_res.json()["session_id"]

    log_entry = await submit_answer(
        db_session, redis_client, uuid.UUID(exam_session_id), uuid.UUID(question_id), "b", uuid.UUID(student_id)
    )
    await _process_submission(str(log_entry.id))

    # No "submit exam" endpoint exists yet (out of this phase's scope) -- the
    # materialized view keys eligibility off exam_session.status, so mark it
    # submitted directly, as a real submit-exam flow eventually would.
    await db_session.execute(
        update(ExamSession)
        .where(ExamSession.id == uuid.UUID(exam_session_id))
        .values(status=ExamSessionStatus.submitted, completed_at=datetime.now(timezone.utc))
    )
    await db_session.commit()

    return {
        "exam_id": exam_id,
        "exam_session_id": exam_session_id,
        "question_id": question_id,
        "instructor_headers": instructor_headers,
        "instructor_id": instructor_id,
        "student_headers": student_headers,
        "student_id": student_id,
        "skill_id": skill_id,
    }
