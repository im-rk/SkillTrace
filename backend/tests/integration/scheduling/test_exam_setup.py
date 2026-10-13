"""What an instructor needs to set an exam up: an informative list, the assigned questions, and re-assignment."""
import pytest

from tests.integration.conftest import create_exam, enroll_student


async def make_question(client, headers, skill_id, prompt, difficulty="easy"):
    res = await client.post(
        "/question-bank/questions",
        json={"skill_id": skill_id, "question_type": "true_false", "prompt": prompt, "difficulty": difficulty, "content": {"correct_answer": True}},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


def assignment(*question_ids):
    return {"questions": [{"question_id": q, "display_order": i + 1, "points": "2.0"} for i, q in enumerate(question_ids)]}


@pytest.mark.asyncio
async def test_list_shows_skill_name_and_counts(client, instructor, student, skill_id):
    headers, _ = instructor
    exam_id = await create_exam(client, headers, skill_id)
    q1, q2 = [await make_question(client, headers, skill_id, f"Q{i}") for i in range(2)]
    assert (await client.post(f"/exams/{exam_id}/questions", json=assignment(q1, q2), headers=headers)).status_code == 204
    await enroll_student(client, headers, exam_id, student[1])

    row = next(e for e in (await client.get("/exams", headers=headers)).json() if e["id"] == exam_id)
    assert row["question_count"] == 2 and row["enrolled_count"] == 1
    assert row["skill_name"].startswith("Skill ") and row["phase"] == "live"


@pytest.mark.asyncio
async def test_a_new_exam_has_zero_questions_and_students(client, instructor, skill_id):
    headers, _ = instructor
    exam_id = await create_exam(client, headers, skill_id)
    row = next(e for e in (await client.get("/exams", headers=headers)).json() if e["id"] == exam_id)
    assert (row["question_count"], row["enrolled_count"]) == (0, 0)


@pytest.mark.asyncio
async def test_instructor_sees_assigned_questions_in_order_with_points(client, instructor, skill_id):
    headers, _ = instructor
    exam_id = await create_exam(client, headers, skill_id)
    first = await make_question(client, headers, skill_id, "First", "easy")
    second = await make_question(client, headers, skill_id, "Second", "hard")
    await client.post(f"/exams/{exam_id}/questions", json=assignment(second, first), headers=headers)

    res = await client.get(f"/exams/{exam_id}/assigned-questions", headers=headers)
    assert res.status_code == 200
    assert [(q["prompt"], q["difficulty"], q["display_order"], float(q["points"])) for q in res.json()] == [
        ("Second", "hard", 1, 2.0),
        ("First", "easy", 2, 2.0),
    ]


@pytest.mark.asyncio
async def test_assigning_again_replaces_the_question_set(client, instructor, skill_id):
    headers, _ = instructor
    exam_id = await create_exam(client, headers, skill_id)
    a, b, c = [await make_question(client, headers, skill_id, name) for name in "ABC"]
    await client.post(f"/exams/{exam_id}/questions", json=assignment(a, b), headers=headers)
    again = await client.post(f"/exams/{exam_id}/questions", json=assignment(b, c), headers=headers)  # b repeats: must not collide
    assert again.status_code == 204, again.text
    prompts = [q["prompt"] for q in (await client.get(f"/exams/{exam_id}/assigned-questions", headers=headers)).json()]
    assert prompts == ["B", "C"]


@pytest.mark.asyncio
async def test_questions_are_locked_once_a_student_has_started(client, started_exam, skill_id):
    headers = started_exam["instructor_headers"]
    extra = await make_question(client, headers, skill_id, "Late addition")
    res = await client.post(f"/exams/{started_exam['exam_id']}/questions", json=assignment(extra), headers=headers)
    assert res.status_code == 409
    assert "already started" in res.json()["detail"]


@pytest.mark.asyncio
async def test_students_cannot_read_assigned_questions(client, instructor, student, skill_id):
    exam_id = await create_exam(client, instructor[0], skill_id)
    assert (await client.get(f"/exams/{exam_id}/assigned-questions", headers=student[0])).status_code == 403
    assert (await client.get(f"/exams/{exam_id}/assigned-questions")).status_code == 401
