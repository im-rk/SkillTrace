import uuid
from datetime import timedelta
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.scheduling import repository
from app.modules.scheduling.models import ExamStatus
from app.modules.scheduling.service import auto_close_expired_exams
from tests.integration.conftest import create_exam


@pytest.mark.asyncio
async def test_close_exam_sets_status_and_dispatches_refresh(mocker, client: AsyncClient, instructor, skill_id):
    instructor_headers, _ = instructor
    delay = mocker.patch("app.modules.scheduling.service.refresh_exam_results_task.delay")
    exam_id = await create_exam(client, instructor_headers, skill_id)

    res = await client.post(f"/exams/{exam_id}/close", headers=instructor_headers)
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "closed"
    delay.assert_called_once_with(exam_id)


@pytest.mark.asyncio
async def test_close_exam_requires_instructor(client: AsyncClient, student, instructor, skill_id):
    instructor_headers, _ = instructor
    student_headers, _ = student
    exam_id = await create_exam(client, instructor_headers, skill_id)

    res = await client.post(f"/exams/{exam_id}/close", headers=student_headers)
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_auto_close_expired_exams_closes_only_past_end_time(
    mocker, client: AsyncClient, db_session: AsyncSession, instructor, skill_id
):
    mocker.patch("app.modules.scheduling.service.refresh_exam_results_task.delay")
    instructor_headers, _ = instructor

    expired_exam_id = await create_exam(
        client, instructor_headers, skill_id, start_offset=timedelta(hours=-2), end_offset=timedelta(minutes=-5)
    )
    open_exam_id = await create_exam(client, instructor_headers, skill_id)

    # The database is shared across tests, so other expired-but-open exams may exist:
    # assert on this test's own exams, not on a global count.
    assert await auto_close_expired_exams(db_session) >= 1

    expired_exam = await repository.get_exam_by_id(db_session, uuid.UUID(expired_exam_id))
    open_exam = await repository.get_exam_by_id(db_session, uuid.UUID(open_exam_id))
    assert expired_exam.status == ExamStatus.closed
    assert open_exam.status != ExamStatus.closed
