import asyncio
from datetime import datetime, timedelta, timezone
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app as fastapi_app
from app.modules.iam.models import UserRole
from tests.integration.conftest import create_exam as _create_exam


@pytest.mark.asyncio
async def test_case_1_manual_enroll_creates_enrollment(client: AsyncClient, instructor, student, skill_id):
    instructor_headers, _ = instructor
    _, student_id = student
    exam_id = await _create_exam(client, instructor_headers, skill_id)

    response = await client.post(
        f"/exams/{exam_id}/enroll", json={"student_id": student_id}, headers=instructor_headers
    )
    assert response.status_code == 201
    data = response.json()
    assert data["exam_id"] == exam_id
    assert data["student_id"] == student_id


@pytest.mark.asyncio
async def test_case_2_enrolled_student_can_start_exam(client: AsyncClient, instructor, student, skill_id):
    instructor_headers, _ = instructor
    student_headers, student_id = student
    exam_id = await _create_exam(client, instructor_headers, skill_id)
    await client.post(f"/exams/{exam_id}/enroll", json={"student_id": student_id}, headers=instructor_headers)

    response = await client.post(f"/exams/{exam_id}/start", headers=student_headers)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_case_4_generate_access_code(client: AsyncClient, instructor, skill_id):
    instructor_headers, _ = instructor
    exam_id = await _create_exam(client, instructor_headers, skill_id)

    response = await client.post(
        f"/exams/{exam_id}/access-codes", json={"max_uses": 50}, headers=instructor_headers
    )
    assert response.status_code == 201
    data = response.json()
    assert len(data["code"]) == 6 and data["code"].isdigit()
    assert data["times_used"] == 0
    assert data["max_uses"] == 50


@pytest.mark.asyncio
async def test_case_5_redeem_valid_code_enrolls_student(client: AsyncClient, instructor, student, skill_id):
    instructor_headers, _ = instructor
    student_headers, _ = student
    exam_id = await _create_exam(client, instructor_headers, skill_id)
    code_res = await client.post(f"/exams/{exam_id}/access-codes", json={"max_uses": 5}, headers=instructor_headers)
    code = code_res.json()["code"]

    response = await client.post(f"/access-codes/{code}/redeem", headers=student_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["enrolled"] is True
    assert data["exam_id"] == exam_id
    assert data["access_method"] == "access_code"


@pytest.mark.asyncio
async def test_case_6_redeem_expired_code_410(client: AsyncClient, instructor, student, skill_id):
    instructor_headers, _ = instructor
    student_headers, _ = student
    exam_id = await _create_exam(client, instructor_headers, skill_id)
    past = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    code_res = await client.post(
        f"/exams/{exam_id}/access-codes", json={"expires_at": past}, headers=instructor_headers
    )
    code = code_res.json()["code"]

    response = await client.post(f"/access-codes/{code}/redeem", headers=student_headers)
    assert response.status_code == 410
    assert "expired" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_case_7_redeem_exhausted_code_410(client: AsyncClient, instructor, student, skill_id, make_user):
    instructor_headers, _ = instructor
    exam_id = await _create_exam(client, instructor_headers, skill_id)
    code_res = await client.post(f"/exams/{exam_id}/access-codes", json={"max_uses": 1}, headers=instructor_headers)
    code = code_res.json()["code"]

    first_headers, _ = student
    first = await client.post(f"/access-codes/{code}/redeem", headers=first_headers)
    assert first.status_code == 200

    second_headers, _ = await make_user(UserRole.student)
    second = await client.post(f"/access-codes/{code}/redeem", headers=second_headers)
    assert second.status_code == 410
    assert "usage limit" in second.json()["detail"].lower()


@pytest.mark.asyncio
async def test_case_8_redeem_same_code_twice_same_student_idempotent(
    client: AsyncClient, db_session: AsyncSession, instructor, student, skill_id
):
    instructor_headers, _ = instructor
    student_headers, _ = student
    exam_id = await _create_exam(client, instructor_headers, skill_id)
    code_res = await client.post(f"/exams/{exam_id}/access-codes", json={"max_uses": 5}, headers=instructor_headers)
    code = code_res.json()["code"]

    first = await client.post(f"/access-codes/{code}/redeem", headers=student_headers)
    second = await client.post(f"/access-codes/{code}/redeem", headers=student_headers)
    assert first.status_code == 200 and second.status_code == 200

    from app.modules.enrollment import repository

    persisted = await repository.get_access_code(db_session, code)
    assert persisted.times_used == 1, "Re-redemption by the same student must not consume a second use"


@pytest.mark.asyncio
async def test_case_10_concurrent_redemption_of_single_use_code_exactly_one_succeeds(
    db_session: AsyncSession, instructor, skill_id, make_user
):
    """Deliberately avoids the shared `client` fixture (pinned to one AsyncSession) —
    see the note in test_concurrent_start_lock.py: truly concurrent requests need
    each its own connection to be a genuine concurrency test."""
    instructor_headers, _ = instructor
    student_a_headers, _ = await make_user(UserRole.student)
    student_b_headers, _ = await make_user(UserRole.student)

    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        exam_id = await _create_exam(client, instructor_headers, skill_id)
        code_res = await client.post(
            f"/exams/{exam_id}/access-codes", json={"max_uses": 1}, headers=instructor_headers
        )
        code = code_res.json()["code"]

        responses = await asyncio.gather(
            client.post(f"/access-codes/{code}/redeem", headers=student_a_headers),
            client.post(f"/access-codes/{code}/redeem", headers=student_b_headers),
        )

    statuses = sorted(r.status_code for r in responses)
    assert statuses == [200, 410], statuses

    from app.modules.enrollment import repository

    persisted = await repository.get_access_code(db_session, code)
    assert persisted.times_used == 1
