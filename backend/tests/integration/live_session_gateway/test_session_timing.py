import pytest
from httpx import AsyncClient

from tests.integration.conftest import create_exam, enroll_student


@pytest.mark.asyncio
async def test_student_gets_own_session_timing(client: AsyncClient, instructor, student, skill_id):
    instructor_headers, _ = instructor
    student_headers, student_id = student
    exam_id = await create_exam(client, instructor_headers, skill_id)
    await enroll_student(client, instructor_headers, exam_id, student_id)

    start_res = await client.post(f"/exams/{exam_id}/start", headers=student_headers)
    assert start_res.status_code == 200, start_res.text
    session_id = start_res.json()["session_id"]

    res = await client.get(f"/exam-sessions/{session_id}/timing", headers=student_headers)
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["total_duration_seconds"] == 60 * 60
    assert 0 <= data["elapsed_active_seconds"] < 10
    assert data["status"] == "in_progress"


@pytest.mark.asyncio
async def test_other_student_cannot_read_session_timing(client: AsyncClient, instructor, student, skill_id, make_user):
    from app.modules.iam.models import UserRole

    instructor_headers, _ = instructor
    student_headers, student_id = student
    exam_id = await create_exam(client, instructor_headers, skill_id)
    await enroll_student(client, instructor_headers, exam_id, student_id)
    start_res = await client.post(f"/exams/{exam_id}/start", headers=student_headers)
    session_id = start_res.json()["session_id"]

    other_headers, _ = await make_user(UserRole.student)
    res = await client.get(f"/exam-sessions/{session_id}/timing", headers=other_headers)
    assert res.status_code == 403
