import pytest
from httpx import AsyncClient

from tests.integration.conftest import create_exam


@pytest.mark.asyncio
async def test_list_enrollments_returns_student_display_name(client: AsyncClient, instructor, student, skill_id):
    instructor_headers, _ = instructor
    student_headers, student_id = student
    exam_id = await create_exam(client, instructor_headers, skill_id)

    enroll_res = await client.post(f"/exams/{exam_id}/enroll", json={"student_id": student_id}, headers=instructor_headers)
    assert enroll_res.status_code == 201

    list_res = await client.get(f"/exams/{exam_id}/enrollments", headers=instructor_headers)
    assert list_res.status_code == 200
    rows = list_res.json()
    assert len(rows) == 1
    assert rows[0]["student_id"] == student_id
    assert rows[0]["display_name"]
    assert rows[0]["email"]

    forbidden = await client.get(f"/exams/{exam_id}/enrollments", headers=student_headers)
    assert forbidden.status_code == 403


@pytest.mark.asyncio
async def test_list_access_codes_for_exam(client: AsyncClient, instructor, skill_id):
    instructor_headers, _ = instructor
    exam_id = await create_exam(client, instructor_headers, skill_id)

    create_res = await client.post(f"/exams/{exam_id}/access-codes", json={}, headers=instructor_headers)
    assert create_res.status_code == 201
    code = create_res.json()["code"]

    list_res = await client.get(f"/exams/{exam_id}/access-codes", headers=instructor_headers)
    assert list_res.status_code == 200
    assert any(c["code"] == code for c in list_res.json())
