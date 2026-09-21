import uuid
from datetime import datetime, timedelta, timezone
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.iam.models import UserRole
from app.modules.quiz_engine.models import Skill


@pytest.fixture
async def instructor(make_user):
    return await make_user(UserRole.instructor)


@pytest.fixture
async def student(make_user):
    return await make_user(UserRole.student)


@pytest.fixture
async def skill_id(db_session: AsyncSession) -> str:
    skill = Skill(name=f"Skill {uuid.uuid4().hex[:6]}", slug=f"skill-{uuid.uuid4().hex[:8]}")
    db_session.add(skill)
    await db_session.commit()
    await db_session.refresh(skill)
    return str(skill.id)


async def create_exam(
    client: AsyncClient,
    instructor_headers: dict,
    skill_id: str,
    start_offset: timedelta = timedelta(minutes=-5),
    end_offset: timedelta = timedelta(minutes=55),
) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "title": "Midterm",
        "skill_id": skill_id,
        "start_time": (now + start_offset).isoformat(),
        "end_time": (now + end_offset).isoformat(),
        "duration_minutes": 60,
    }
    res = await client.post("/exams", json=payload, headers=instructor_headers)
    assert res.status_code == 201, res.text
    return res.json()["id"]


async def enroll_student(client: AsyncClient, instructor_headers: dict, exam_id: str, student_id: str) -> None:
    res = await client.post(f"/exams/{exam_id}/enroll", json={"student_id": student_id}, headers=instructor_headers)
    assert res.status_code == 201, res.text


@pytest.fixture
async def started_exam(client: AsyncClient, instructor, student, skill_id):
    """An enrolled student with a started (in_progress) session on an exam with
    two MCQ questions (correct choice "b"), ready to answer."""
    instructor_headers, _ = instructor
    student_headers, student_id = student

    exam_id = await create_exam(client, instructor_headers, skill_id)
    await enroll_student(client, instructor_headers, exam_id, student_id)

    question_ids = []
    for prompt in ("What is 2 + 2?", "What is 3 + 3?"):
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
        question_ids.append(res.json()["id"])

    assign = await client.post(
        f"/exams/{exam_id}/questions",
        json={"questions": [{"question_id": q, "display_order": i + 1, "points": "1.0"} for i, q in enumerate(question_ids)]},
        headers=instructor_headers,
    )
    assert assign.status_code == 204, assign.text

    start = await client.post(f"/exams/{exam_id}/start", headers=student_headers)
    assert start.status_code == 200, start.text
    return {
        "exam_id": exam_id,
        "session_id": start.json()["session_id"],
        "question_ids": question_ids,
        "instructor_headers": instructor_headers,
        "student_headers": student_headers,
        "student_id": student_id,
    }
