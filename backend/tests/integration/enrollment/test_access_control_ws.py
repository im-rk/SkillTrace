"""
Test WebSocket handshake rejection for unauthorized users.

verify_exam_access_ws never raises -- it returns None on every failure mode,
since the caller (Phase 8's ws_routes.py) is responsible for closing the
connection based on a None result, before accepting it.
"""
import uuid
from datetime import datetime, timedelta, timezone
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.enrollment import repository as enrollment_repository
from app.modules.enrollment.deps import verify_exam_access_ws
from app.modules.iam.models import UserRole
from app.modules.iam.service import create_access_token
from app.modules.scheduling.models import Exam


class FakeWebSocket:
    """Minimal stand-in -- verify_exam_access_ws only ever reads query_params/cookies."""

    def __init__(self, token: str | None):
        self.query_params = {"token": token} if token is not None else {}
        self.cookies = {}


@pytest.fixture
async def exam_id(db_session: AsyncSession, instructor, skill_id: str) -> str:
    _, instructor_id = instructor
    now = datetime.now(timezone.utc)
    exam = Exam(
        title="WS Exam",
        skill_id=uuid.UUID(skill_id),
        start_time=now - timedelta(minutes=5),
        end_time=now + timedelta(minutes=55),
        duration_minutes=60,
        created_by=uuid.UUID(instructor_id),
    )
    db_session.add(exam)
    await db_session.commit()
    await db_session.refresh(exam)
    return str(exam.id)


@pytest.mark.asyncio
async def test_no_token_returns_none(db_session: AsyncSession, exam_id):
    result = await verify_exam_access_ws(FakeWebSocket(None), uuid.UUID(exam_id), db_session)
    assert result is None


@pytest.mark.asyncio
async def test_malformed_token_returns_none(db_session: AsyncSession, exam_id):
    result = await verify_exam_access_ws(FakeWebSocket("not.a.valid.jwt"), uuid.UUID(exam_id), db_session)
    assert result is None


@pytest.mark.asyncio
async def test_expired_token_returns_none(db_session: AsyncSession, exam_id):
    token = create_access_token(
        data={"sub": str(uuid.uuid4()), "role": "student"}, expires_delta=timedelta(seconds=-60)
    )
    result = await verify_exam_access_ws(FakeWebSocket(token), uuid.UUID(exam_id), db_session)
    assert result is None


@pytest.mark.asyncio
async def test_valid_token_but_unenrolled_returns_none(db_session: AsyncSession, exam_id, make_user):
    student_headers, _ = await make_user(UserRole.student)
    token = student_headers["Authorization"].split(" ")[1]

    result = await verify_exam_access_ws(FakeWebSocket(token), uuid.UUID(exam_id), db_session)
    assert result is None


@pytest.mark.asyncio
async def test_valid_token_and_enrolled_returns_user(db_session: AsyncSession, exam_id, make_user):
    student_headers, student_id = await make_user(UserRole.student)
    token = student_headers["Authorization"].split(" ")[1]
    await enrollment_repository.create_enrollment(db_session, uuid.UUID(exam_id), uuid.UUID(student_id))
    await db_session.commit()

    result = await verify_exam_access_ws(FakeWebSocket(token), uuid.UUID(exam_id), db_session)
    assert result is not None
    assert str(result.user_id) == student_id
