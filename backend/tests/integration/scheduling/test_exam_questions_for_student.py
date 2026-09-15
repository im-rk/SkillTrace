import pytest
from httpx import AsyncClient

from tests.integration.conftest import create_exam, enroll_student


@pytest.fixture
async def exam_with_mcq(client: AsyncClient, instructor, skill_id):
    instructor_headers, _ = instructor
    exam_id = await create_exam(client, instructor_headers, skill_id)

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

    return exam_id, question_id


@pytest.mark.asyncio
async def test_enrolled_student_sees_questions_without_correct_answer(
    client: AsyncClient, instructor, student, exam_with_mcq
):
    instructor_headers, _ = instructor
    student_headers, student_id = student
    exam_id, question_id = exam_with_mcq
    await enroll_student(client, instructor_headers, exam_id, student_id)

    res = await client.get(f"/exams/{exam_id}/questions", headers=student_headers)
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["exam_id"] == exam_id
    assert len(data["questions"]) == 1
    question = data["questions"][0]
    assert question["question_id"] == question_id
    assert question["content"] == {"choices": [{"id": "a", "text": "3"}, {"id": "b", "text": "4"}]}
    assert "correct_choice_id" not in question["content"]


@pytest.mark.asyncio
async def test_unenrolled_student_gets_403(client: AsyncClient, student, exam_with_mcq):
    student_headers, _ = student
    exam_id, _ = exam_with_mcq

    res = await client.get(f"/exams/{exam_id}/questions", headers=student_headers)
    assert res.status_code == 403
