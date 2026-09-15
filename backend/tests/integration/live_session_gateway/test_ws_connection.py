"""
Pre-accept authorization ordering for the exam-session WebSocket endpoint.
See docs/adr/0010-websocket-authorization-ordering.md -- test cases 2-4's
accept()-call-count assertion is the single most important check in this
phase, more so than the close-code checks alongside it.
"""
import uuid
from datetime import timedelta
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
