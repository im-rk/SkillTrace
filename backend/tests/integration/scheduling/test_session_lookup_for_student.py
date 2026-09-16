import uuid
import pytest
from httpx import AsyncClient

from tests.integration.conftest import create_exam, enroll_student


@pytest.mark.asyncio
async def test_instructor_looks_up_a_students_session_id(client: AsyncClient, instructor, student, skill_id):
    instructor_headers, _ = instructor
    student_headers, student_id = student
    exam_id = await create_exam(client, instructor_headers, skill_id)
    await enroll_student(client, instructor_headers, exam_id, student_id)

    start_res = await client.post(f"/exams/{exam_id}/start", headers=student_headers)
    session_id = start_res.json()["session_id"]

    res = await client.get(f"/exams/{exam_id}/students/{student_id}/session", headers=instructor_headers)
    assert res.status_code == 200, res.text
    assert res.json()["session_id"] == session_id


@pytest.mark.asyncio
async def test_lookup_for_student_with_no_session_is_404(client: AsyncClient, instructor, student, skill_id):
    instructor_headers, _ = instructor
    _, student_id = student
    exam_id = await create_exam(client, instructor_headers, skill_id)

    res = await client.get(f"/exams/{exam_id}/students/{student_id}/session", headers=instructor_headers)
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_lookup_requires_instructor(client: AsyncClient, student, skill_id, instructor):
    instructor_headers, _ = instructor
    student_headers, student_id = student
    exam_id = await create_exam(client, instructor_headers, skill_id)

    res = await client.get(f"/exams/{exam_id}/students/{student_id}/session", headers=student_headers)
    assert res.status_code == 403
