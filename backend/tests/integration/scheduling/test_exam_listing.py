import pytest
from httpx import AsyncClient

from tests.integration.conftest import create_exam


@pytest.mark.asyncio
async def test_instructor_lists_and_gets_exam(client: AsyncClient, instructor, skill_id):
    instructor_headers, _ = instructor
    exam_id = await create_exam(client, instructor_headers, skill_id)

    list_res = await client.get("/exams", headers=instructor_headers)
    assert list_res.status_code == 200
    assert any(e["id"] == exam_id for e in list_res.json())

    get_res = await client.get(f"/exams/{exam_id}", headers=instructor_headers)
    assert get_res.status_code == 200
    assert get_res.json()["id"] == exam_id


@pytest.mark.asyncio
async def test_student_cannot_list_exams(client: AsyncClient, student):
    student_headers, _ = student
    res = await client.get("/exams", headers=student_headers)
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_get_nonexistent_exam_404(client: AsyncClient, instructor):
    import uuid

    instructor_headers, _ = instructor
    res = await client.get(f"/exams/{uuid.uuid4()}", headers=instructor_headers)
    assert res.status_code == 404
