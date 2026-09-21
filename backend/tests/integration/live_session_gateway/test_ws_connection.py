"""
Pre-accept authorization ordering for the exam-session WebSocket endpoint.
See docs/adr/0010-websocket-authorization-ordering.md -- test cases 2-4's
accept()-call-count assertion is the single most important check in this
phase, more so than the close-code checks alongside it.
"""
import uuid
from datetime import datetime, timedelta, timezone
import pytest
from fastapi import WebSocket
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.main import app as fastapi_app
from app.modules.iam.models import UserRole
from app.modules.iam.service import create_access_token
from app.modules.live_session_gateway.websocket_manager import connection_manager


@pytest.mark.asyncio
async def test_case_1_enrolled_user_connection_accepted_and_registered(ws_session):
    with TestClient(fastapi_app) as client:
        with client.websocket_connect(
            f"/ws/exam-sessions/{ws_session['session_id']}?token={ws_session['token']}"
        ):
            assert connection_manager._connections.get(ws_session["session_id"]) is not None


@pytest.mark.asyncio
async def test_case_2_unenrolled_user_rejected_before_accept(mocker, ws_session, make_user):
    outsider_headers, _ = await make_user(UserRole.student)
    outsider_token = outsider_headers["Authorization"].split(" ")[1]

    accept_spy = mocker.spy(WebSocket, "accept")
    with TestClient(fastapi_app) as client:
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect(f"/ws/exam-sessions/{ws_session['session_id']}?token={outsider_token}"):
                pass

    assert exc_info.value.code == 4403
    assert accept_spy.call_count == 0, "accept() must never be called for a rejected connection"


@pytest.mark.asyncio
async def test_case_3_no_token_rejected_before_accept(mocker, ws_session):
    accept_spy = mocker.spy(WebSocket, "accept")
    with TestClient(fastapi_app) as client:
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect(f"/ws/exam-sessions/{ws_session['session_id']}"):
                pass

    assert exc_info.value.code == 4403
    assert accept_spy.call_count == 0


@pytest.mark.asyncio
async def test_case_4_expired_token_rejected_before_accept(mocker, ws_session):
    expired_token = create_access_token(
        data={"sub": ws_session["student_id"], "role": "student"}, expires_delta=timedelta(seconds=-60)
    )

    accept_spy = mocker.spy(WebSocket, "accept")
    with TestClient(fastapi_app) as client:
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect(f"/ws/exam-sessions/{ws_session['session_id']}?token={expired_token}"):
                pass

    assert exc_info.value.code == 4403
    assert accept_spy.call_count == 0


@pytest.mark.asyncio
async def test_unknown_session_id_rejected_4404(mocker):
    accept_spy = mocker.spy(WebSocket, "accept")
    with TestClient(fastapi_app) as client:
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect(f"/ws/exam-sessions/{uuid.uuid4()}?token=irrelevant"):
                pass

    assert exc_info.value.code == 4404
    assert accept_spy.call_count == 0


@pytest.mark.asyncio
async def test_enrolled_student_cannot_connect_to_another_students_session(mocker, ws_session, db_session, make_user):
    """Being enrolled in the exam is not enough: the session must be the caller's own."""
    from app.modules.enrollment import repository as enrollment_repository

    other_headers, other_id = await make_user(UserRole.student)
    await enrollment_repository.create_enrollment(db_session, uuid.UUID(ws_session["exam_id"]), uuid.UUID(other_id))
    await db_session.commit()
    other_token = other_headers["Authorization"].split(" ")[1]

    accept_spy = mocker.spy(WebSocket, "accept")
    with TestClient(fastapi_app) as client:
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect(f"/ws/exam-sessions/{ws_session['session_id']}?token={other_token}"):
                pass

    assert exc_info.value.code == 4403
    assert accept_spy.call_count == 0


@pytest.mark.asyncio
async def test_connecting_to_an_ended_session_immediately_receives_time_up(ws_session, db_session):
    from app.modules.live_session_gateway.service import auto_submit_expired_sessions  # noqa: F401
    from app.modules.live_session_gateway import repository as gateway_repository
    from app.modules.live_session_gateway.models import ExamSessionStatus

    session = await gateway_repository.get_session(db_session, uuid.UUID(ws_session["session_id"]))
    session.status = ExamSessionStatus.auto_submitted
    await db_session.commit()

    with TestClient(fastapi_app) as client:
        with client.websocket_connect(
            f"/ws/exam-sessions/{ws_session['session_id']}?token={ws_session['token']}"
        ) as ws:
            message = ws.receive_json()

    assert message["type"] == "time_up"
    assert message["session_id"] == ws_session["session_id"]


@pytest.mark.asyncio
async def test_connecting_resumes_a_paused_session(ws_session, db_session):
    from datetime import datetime, timezone
    from app.modules.live_session_gateway import repository as gateway_repository
    from app.modules.live_session_gateway import service as gateway_service
    from app.modules.live_session_gateway.models import ExamSessionStatus

    import asyncio

    session_id = uuid.UUID(ws_session["session_id"])
    await gateway_service.pause_session(db_session, session_id, datetime.now(timezone.utc))

    status = None
    with TestClient(fastapi_app) as client:
        with client.websocket_connect(f"/ws/exam-sessions/{ws_session['session_id']}?token={ws_session['token']}"):
            # No heartbeat message is sent: connecting is itself the heartbeat.
            for _ in range(50):
                await db_session.rollback()  # end the open transaction so we read fresh data
                session = await gateway_repository.get_session(db_session, session_id)
                await db_session.refresh(session)
                status = session.status
                if status == ExamSessionStatus.in_progress:
                    break
                await asyncio.sleep(0.1)

    assert status == ExamSessionStatus.in_progress


@pytest.mark.asyncio
async def test_state_transitions_never_act_on_a_stale_cached_session(ws_session, db_session):
    """Regression (found in a real browser): the WebSocket handler keeps ONE DB
    session for the whole connection, so its identity map holds an ExamSession
    that is stale once the student submits from another request. On disconnect
    it paused that stale `in_progress` copy, overwriting the final `submitted`
    status -- and on reload the student was let back into a finished exam."""
    from app.core.db.session import async_session_maker
    from app.modules.live_session_gateway import repository as gateway_repository
    from app.modules.live_session_gateway import service as gateway_service
    from app.modules.live_session_gateway.models import ExamSessionStatus

    session_id = uuid.UUID(ws_session["session_id"])
    # The WS handler's session loads the session at connect time...
    cached = await gateway_repository.get_session(db_session, session_id)
    assert cached.status == ExamSessionStatus.in_progress

    # ...the student then submits through a different request/session...
    async with async_session_maker() as other:
        await gateway_service.submit_exam_session(other, session_id, uuid.UUID(ws_session["student_id"]))

    # ...and the socket's later disconnect / heartbeat handlers must see the truth.
    await gateway_service.pause_session(db_session, session_id, datetime.now(timezone.utc))
    await gateway_service.update_heartbeat(db_session, session_id)

    await db_session.rollback()
    final = await gateway_repository.get_session(db_session, session_id)
    await db_session.refresh(final)
    assert final.status == ExamSessionStatus.submitted
