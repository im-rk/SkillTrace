"""
Item analysis endpoint: real p-value/discrimination computed from a graded exam
with multiple students of varying performance.
"""
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import update

from app.modules.evaluation_pipeline.queue_producer import submit_answer
from app.modules.evaluation_pipeline.tasks import _process_submission
from app.modules.iam.models import UserRole
from app.modules.live_session_gateway.models import ExamSession, ExamSessionStatus
from app.modules.results.refresh_service import refresh_exam_results
from tests.integration.conftest import create_exam, enroll_student

DISCRIMINATING = "b"  # only strong students get this one right
EASY = "b"  # everyone gets this one right


@pytest.fixture
async def scored_exam(client, db_session, redis_client, instructor, skill_id, make_user):
    """One exam, two MCQ questions, 10 students. 5 "strong" students answer both
    correctly; 5 "weak" students get the discriminating question wrong (but still
    get the easy one right) -- a textbook-shaped scenario with a known answer."""
    instructor_headers, _ = instructor

    exam_id = await create_exam(client, instructor_headers, skill_id)
    questions = []
    for prompt in ("Easy question", "Discriminating question"):
        res = await client.post(
            "/question-bank/questions",
            json={
                "skill_id": skill_id,
                "question_type": "multiple_choice",
                "prompt": prompt,
                "difficulty": "easy",
                "content": {"choices": [{"id": "a", "text": "x"}, {"id": "b", "text": "y"}], "correct_choice_id": "b"},
            },
            headers=instructor_headers,
        )
        assert res.status_code == 201, res.text
        questions.append(res.json()["id"])
    easy_id, discriminating_id = questions

    assign = await client.post(
        f"/exams/{exam_id}/questions",
        json={"questions": [{"question_id": q, "display_order": i + 1, "points": "1.0"} for i, q in enumerate(questions)]},
        headers=instructor_headers,
    )
    assert assign.status_code == 204, assign.text

    students = []
    for i in range(10):
        headers, student_id = await make_user(UserRole.student)
        await enroll_student(client, instructor_headers, exam_id, student_id)
        start = await client.post(f"/exams/{exam_id}/start", headers=headers)
        assert start.status_code == 200, start.text
        session_id = start.json()["session_id"]

        strong = i < 5
        for question_id, answer in ((easy_id, "b"), (discriminating_id, "b" if strong else "a")):
            log = await submit_answer(db_session, redis_client, uuid.UUID(session_id), uuid.UUID(question_id), answer, uuid.UUID(student_id))
            await _process_submission(str(log.id))

        await db_session.execute(
            update(ExamSession)
            .where(ExamSession.id == uuid.UUID(session_id))
            .values(status=ExamSessionStatus.submitted, completed_at=datetime.now(timezone.utc))
        )
        await db_session.commit()
        students.append({"student_id": student_id, "strong": strong})

    await refresh_exam_results(db_session)
    return {
        "exam_id": exam_id,
        "instructor_headers": instructor_headers,
        "easy_id": easy_id,
        "discriminating_id": discriminating_id,
        "students": students,
    }


@pytest.mark.asyncio
async def test_item_analysis_p_value_and_discrimination_match_the_known_scenario(client, scored_exam):
    res = await client.get(f"/exams/{scored_exam['exam_id']}/item-analysis", headers=scored_exam["instructor_headers"])
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["exam_id"] == scored_exam["exam_id"]
    by_id = {item["question_id"]: item for item in body["items"]}

    easy = by_id[scored_exam["easy_id"]]
    assert easy["sample_size"] == 10
    assert easy["p_value"] == pytest.approx(1.0)
    assert easy["discrimination"] == pytest.approx(0.0)  # everyone got it right -> no discriminating power

    hard = by_id[scored_exam["discriminating_id"]]
    assert hard["sample_size"] == 10
    assert hard["p_value"] == pytest.approx(0.5)  # 5 of 10 correct
    assert hard["discrimination"] == pytest.approx(1.0)  # perfectly separates strong from weak
    assert hard["prompt"] == "Discriminating question"


@pytest.mark.asyncio
async def test_item_analysis_is_instructor_only(client, scored_exam, student):
    student_headers, _ = student
    assert (await client.get(f"/exams/{scored_exam['exam_id']}/item-analysis", headers=student_headers)).status_code == 403
    assert (await client.get(f"/exams/{scored_exam['exam_id']}/item-analysis")).status_code == 401


@pytest.mark.asyncio
async def test_item_analysis_on_an_exam_nobody_has_taken_is_an_empty_list(client, instructor, skill_id):
    instructor_headers, _ = instructor
    exam_id = await create_exam(client, instructor_headers, skill_id)
    res = await client.get(f"/exams/{exam_id}/item-analysis", headers=instructor_headers)
    assert res.status_code == 200 and res.json()["items"] == []
