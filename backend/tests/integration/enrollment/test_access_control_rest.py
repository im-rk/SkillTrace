"""
Test verify_exam_access 403 cases for REST endpoints.
"""
import pytest
from httpx import AsyncClient

from tests.integration.conftest import create_exam


@pytest.mark.asyncio
async def test_unenrolled_student_403(client: AsyncClient, instructor, student, skill_id):
    instructor_headers, _ = instructor
    student_headers, _ = student
    exam_id = await create_exam(client, instructor_headers, skill_id)

    response = await client.post(f"/exams/{exam_id}/start", headers=student_headers)
    assert response.status_code == 403
    assert response.json()["detail"] == "Not enrolled in this exam"


@pytest.mark.asyncio
async def test_unenrolled_student_never_triggers_session_creation(
    mocker, client: AsyncClient, instructor, student, skill_id
):
    """The 'before further data is touched' proof (Section 3.4 of the phase spec):
    a 403 for an unenrolled student must come from the enrollment check alone,
    with no exam_session row ever created downstream."""
    from app.modules.scheduling import repository as scheduling_repository

    instructor_headers, _ = instructor
    student_headers, _ = student
    exam_id = await create_exam(client, instructor_headers, skill_id)

    create_session_spy = mocker.spy(scheduling_repository, "create_exam_session")
    response = await client.post(f"/exams/{exam_id}/start", headers=student_headers)

    assert response.status_code == 403
    assert create_session_spy.call_count == 0, "No exam session may be created for an unenrolled user"
