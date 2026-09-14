"""
Test simulating N concurrent start-exam requests.

These tests deliberately do NOT use the shared `client` fixture used elsewhere:
it pins every request to one single AsyncSession, which cannot safely serve
truly concurrent asyncpg queries. A raw ASGI client (no get_db override) lets
each request open its own connection from the app's real pool, which is what
makes this a genuine concurrency test rather than one that would "pass" even
with a completely broken lock. `db_session` (and fixtures built on it, like
`make_user`/`skill_id`) is still used for setup and for the final DB-count
assertion, since those happen outside the concurrent request burst.
"""
import asyncio
import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app as fastapi_app
from app.modules.iam.models import UserRole
from app.modules.live_session_gateway.models import ExamSession
from tests.integration.scheduling.conftest import create_exam


async def _count_exam_sessions(db_session: AsyncSession, exam_id: str, student_id: str) -> int:
    result = await db_session.execute(
        select(ExamSession).where(ExamSession.exam_id == exam_id, ExamSession.student_id == student_id)
    )
    return len(result.scalars().all())


@pytest.mark.asyncio
async def test_concurrent_start_requests_create_exactly_one_session(db_session: AsyncSession, make_user, skill_id):
    instructor_headers, _ = await make_user(UserRole.instructor)
    student_headers, student_id = await make_user(UserRole.student)

    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        exam_id = await create_exam(client, instructor_headers, skill_id)

        async def attempt_start():
            return await client.post(f"/exams/{exam_id}/start", headers=student_headers)

        responses = await asyncio.gather(*[attempt_start() for _ in range(20)])

    success_count = sum(1 for r in responses if r.status_code == 200)
    session_ids = {r.json()["session_id"] for r in responses if r.status_code == 200}

    assert success_count == 20, [r.status_code for r in responses]
    assert len(session_ids) == 1, f"Expected 1 unique session, got {len(session_ids)}"

    db_session_count = await _count_exam_sessions(db_session, exam_id, student_id)
    assert db_session_count == 1


@pytest.mark.asyncio
async def test_different_students_start_concurrently_get_independent_sessions(db_session: AsyncSession, make_user, skill_id):
    instructor_headers, _ = await make_user(UserRole.instructor)
    students = [await make_user(UserRole.student) for _ in range(5)]

    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        exam_id = await create_exam(client, instructor_headers, skill_id)

        async def attempt_start(headers):
            return await client.post(f"/exams/{exam_id}/start", headers=headers)

        responses = await asyncio.gather(*[attempt_start(headers) for headers, _ in students])

    assert all(r.status_code == 200 for r in responses)
    session_ids = {r.json()["session_id"] for r in responses}
    assert len(session_ids) == 5
