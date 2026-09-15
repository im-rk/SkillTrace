import uuid
import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.evaluation_pipeline.models import SubmissionQueueLog
from app.modules.evaluation_pipeline.queue_producer import SUBMISSIONS_STREAM, submit_answer
from tests.integration.conftest import create_exam, enroll_student


@pytest_asyncio.fixture(autouse=True)
async def _clean_submissions_stream(redis_client):
    """stream:submissions is real, shared Redis state across the whole test
    session -- without this, an earlier test's undelivered messages would
    still be sitting in the stream/consumer group and get read by a later
    test's XREADGROUP call ahead of that test's own message."""
    await redis_client.delete(SUBMISSIONS_STREAM)
    yield
    await redis_client.delete(SUBMISSIONS_STREAM)


@pytest.fixture
async def submission_setup(client: AsyncClient, db_session: AsyncSession, instructor, student, skill_id):
    """An enrolled student with a started exam session and one assigned MCQ
    question worth 2.0 points, ready to submit-answer against."""
    instructor_headers, _ = instructor
    student_headers, student_id = student

    exam_id = await create_exam(client, instructor_headers, skill_id)
    await enroll_student(client, instructor_headers, exam_id, student_id)

    question_payload = {
        "skill_id": skill_id,
        "question_type": "multiple_choice",
        "prompt": "What is 2 + 2?",
        "difficulty": "easy",
        "content": {
            "choices": [{"id": "a", "text": "3"}, {"id": "b", "text": "4"}],
            "correct_choice_id": "b",
        },
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

    return {
        "exam_id": exam_id,
        "exam_session_id": exam_session_id,
        "question_id": question_id,
        "correct_answer": "b",
        "wrong_answer": "a",
        "student_headers": student_headers,
        "student_id": student_id,
        "skill_id": skill_id,
    }


async def submit_for_setup(
    db_session: AsyncSession, redis_client, setup: dict, answer: str
) -> SubmissionQueueLog:
    """Shared shortcut used by both test_submission.py and
    test_queue_durability.py: calls the real queue_producer.submit_answer
    against a `submission_setup` fixture's session/question/student."""
    return await submit_answer(
        db_session,
        redis_client,
        uuid.UUID(setup["exam_session_id"]),
        uuid.UUID(setup["question_id"]),
        answer,
        uuid.UUID(setup["student_id"]),
    )
