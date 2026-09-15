import uuid
from datetime import timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.main import app as fastapi_app
from app.modules.live_session_gateway import repository, service
from app.modules.live_session_gateway.models import ExamSessionStatus


@pytest.mark.asyncio
async def test_case_6_heartbeat_updates_last_heartbeat_at(db_session: AsyncSession, ws_session):
    session_id = uuid.UUID(ws_session["session_id"])
    before = await repository.get_session(db_session, session_id)
    original_heartbeat = before.last_heartbeat_at

    with TestClient(fastapi_app) as client:
        with client.websocket_connect(
            f"/ws/exam-sessions/{ws_session['session_id']}?token={ws_session['token']}"
        ) as ws:
            ws.send_json({"type": "heartbeat"})
            ack = ws.receive_json()
            assert ack == {"type": "heartbeat_ack"}

    # The identity map would otherwise hand back the same cached object with
    # its original attributes -- refresh explicitly to see the update the
    # WebSocket connection committed on a different connection.
    await db_session.refresh(before)
    assert before.last_heartbeat_at > original_heartbeat


@pytest.mark.asyncio
async def test_case_7_stale_session_gets_flagged_paused(db_session: AsyncSession, ws_session):
    session_id = uuid.UUID(ws_session["session_id"])
    exam_session = await repository.get_session(db_session, session_id)
    exam_session.last_heartbeat_at = exam_session.started_at - timedelta(
        seconds=settings.STALE_SESSION_THRESHOLD_SECONDS + 5
    )
    await db_session.commit()

    flagged_count = await service.flag_stale_sessions(db_session)
    assert flagged_count >= 1

    refreshed = await repository.get_session(db_session, session_id)
    assert refreshed.status == ExamSessionStatus.paused_disconnected


@pytest.mark.asyncio
async def test_case_8_reconnect_resumes_and_elapsed_time_excludes_paused_window(
    db_session: AsyncSession, ws_session
):
    session_id = uuid.UUID(ws_session["session_id"])
    exam_session = await repository.get_session(db_session, session_id)
    started_at = exam_session.started_at

    # Session went stale 20s in, flagged paused, reconnects 10s of "outage" later.
    paused_at = started_at + timedelta(seconds=20)
    await service.pause_session(db_session, session_id, paused_at)

    refreshed = await repository.get_session(db_session, session_id)
    assert refreshed.status == ExamSessionStatus.paused_disconnected

    resumed_at = paused_at + timedelta(seconds=10)
    await service.resume_session(db_session, session_id, resumed_at)

    refreshed = await repository.get_session(db_session, session_id)
    assert refreshed.status == ExamSessionStatus.in_progress

    # Freeze a deterministic end-of-session point for the elapsed-time snapshot.
    refreshed.completed_at = resumed_at + timedelta(seconds=5)
    await db_session.commit()

    elapsed = await service.compute_elapsed_active_time(db_session, session_id)
    # Wall time (completed_at - started_at) = 35s; the 10s paused window is excluded.
    assert elapsed == timedelta(seconds=25)
