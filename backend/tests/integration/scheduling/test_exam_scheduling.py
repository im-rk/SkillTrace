import uuid
from datetime import timedelta
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.iam.models import UserRole
from tests.integration.scheduling.conftest import create_exam


@pytest.fixture
async def instructor(make_user):
    return await make_user(UserRole.instructor)


@pytest.fixture
async def student(make_user):
    return await make_user(UserRole.student)


@pytest.mark.asyncio
async def test_case_1_start_within_window_creates_session(client: AsyncClient, instructor, student, skill_id):
    instructor_headers, _ = instructor
    student_headers, _ = student
    exam_id = await create_exam(client, instructor_headers, skill_id)

    response = await client.post(f"/exams/{exam_id}/start", headers=student_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["exam_id"] == exam_id
    assert data["status"] == "in_progress"


@pytest.mark.asyncio
async def test_case_2_restart_returns_same_session(client: AsyncClient, instructor, student, skill_id):
    instructor_headers, _ = instructor
    student_headers, _ = student
    exam_id = await create_exam(client, instructor_headers, skill_id)

    first = await client.post(f"/exams/{exam_id}/start", headers=student_headers)
    second = await client.post(f"/exams/{exam_id}/start", headers=student_headers)
    assert first.status_code == 200 and second.status_code == 200
    assert first.json()["session_id"] == second.json()["session_id"]


@pytest.mark.asyncio
async def test_case_3_start_before_window_409(client: AsyncClient, instructor, student, skill_id):
    instructor_headers, _ = instructor
    student_headers, _ = student
    exam_id = await create_exam(client, instructor_headers, skill_id, timedelta(hours=1), timedelta(hours=2))

    response = await client.post(f"/exams/{exam_id}/start", headers=student_headers)
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_case_4_start_after_window_409(client: AsyncClient, instructor, student, skill_id):
    instructor_headers, _ = instructor
    student_headers, _ = student
    exam_id = await create_exam(client, instructor_headers, skill_id, timedelta(hours=-2), timedelta(hours=-1))

    response = await client.post(f"/exams/{exam_id}/start", headers=student_headers)
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_case_6_unique_constraint_backstops_duplicate_session(db_session: AsyncSession, instructor, student, skill_id, client):
    instructor_headers, _ = instructor
    student_headers, student_id = student
    exam_id = await create_exam(client, instructor_headers, skill_id)

    from app.modules.scheduling import repository
    from sqlalchemy.exc import IntegrityError

    await repository.create_exam_session(db_session, uuid.UUID(exam_id), uuid.UUID(student_id))
    with pytest.raises(IntegrityError):
        await repository.create_exam_session(db_session, uuid.UUID(exam_id), uuid.UUID(student_id))
