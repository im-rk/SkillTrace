import uuid
from datetime import datetime, timedelta, timezone
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.enrollment import repository as enrollment_repository
from app.modules.scheduling import repository as scheduling_repository
from app.modules.scheduling.models import Exam


@pytest_asyncio.fixture(autouse=True)
async def _dispose_app_engine_after_test():
    """Starlette's TestClient runs the app in its own thread with its own event
    loop per `with TestClient(...)` block. The app's real connection pool
    (app.core.db.session.engine) is a module-level singleton, so a pooled
    connection opened on one test's TestClient loop is dead once that loop
    closes -- reusing it in the next test raises "Event loop is closed".
    Disposing the pool after every test in this package forces a fresh
    connection (and loop binding) next time."""
    yield
    from app.core.db.session import engine

    await engine.dispose()


@pytest.fixture
async def ws_session(db_session: AsyncSession, instructor, student, skill_id):
    """An enrolled student with a live ExamSession, plus their raw JWT for the
    WebSocket query string. Built via direct ORM/repository calls (like
    test_access_control_ws.py) rather than the REST `client` fixture: the
    WebSocket tests use Starlette's TestClient, which runs the app in its own
    thread/event loop, so they must go through the app's real get_db -- reusing
    the `client` fixture's db_session override here would leak across loops."""
    _, instructor_id = instructor
    student_headers, student_id = student

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

    await enrollment_repository.create_enrollment(db_session, exam.id, uuid.UUID(student_id))
    await db_session.commit()

    exam_session = await scheduling_repository.create_exam_session(db_session, exam.id, uuid.UUID(student_id))

    token = student_headers["Authorization"].split(" ")[1]
    return {
        "session_id": str(exam_session.id),
        "exam_id": str(exam.id),
        "student_id": student_id,
        "token": token,
    }
