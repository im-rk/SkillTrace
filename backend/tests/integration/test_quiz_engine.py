import uuid
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_instructor_creates_skill_and_lists_it(client: AsyncClient, instructor):
    instructor_headers, _ = instructor
    slug = f"algebra-{uuid.uuid4().hex[:8]}"

    create_res = await client.post(
        "/skills", json={"name": "Algebra", "slug": slug, "description": "Basic algebra"}, headers=instructor_headers
    )
    assert create_res.status_code == 201, create_res.text
    skill_id = create_res.json()["id"]

    list_res = await client.get("/skills", headers=instructor_headers)
    assert list_res.status_code == 200
    assert any(s["id"] == skill_id for s in list_res.json())


@pytest.mark.asyncio
async def test_student_cannot_create_skill(client: AsyncClient, student):
    student_headers, _ = student
    res = await client.post(
        "/skills", json={"name": "Algebra", "slug": f"algebra-{uuid.uuid4().hex[:8]}"}, headers=student_headers
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_duplicate_slug_is_409(client: AsyncClient, instructor):
    instructor_headers, _ = instructor
    slug = f"dup-{uuid.uuid4().hex[:8]}"
    payload = {"name": "Dup", "slug": slug}

    first = await client.post("/skills", json=payload, headers=instructor_headers)
    assert first.status_code == 201

    second = await client.post("/skills", json=payload, headers=instructor_headers)
    assert second.status_code == 409
