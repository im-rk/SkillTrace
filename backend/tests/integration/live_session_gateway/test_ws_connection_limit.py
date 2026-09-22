"""
Phase 13: a session may hold one live WebSocket. A second one is refused with its
own close code (4409, not the 4403 of an authorization failure), unless the first
has stopped heartbeating -- then it is presumed dead and replaced, so a half-open
socket after a network drop can't lock a student out of their own exam.
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import update
from starlette.websockets import WebSocketDisconnect

from app.main import app as fastapi_app
from app.modules.live_session_gateway.models import ExamSession
from app.modules.live_session_gateway.websocket_manager import connection_manager


@pytest.mark.asyncio
async def test_case_4_second_live_connection_for_a_session_is_rejected_with_its_own_code(ws_session):
    url = f"/ws/exam-sessions/{ws_session['session_id']}?token={ws_session['token']}"
    with TestClient(fastapi_app) as client:
        with client.websocket_connect(url):
            with pytest.raises(WebSocketDisconnect) as exc_info:
                with client.websocket_connect(url):
                    pass
            assert exc_info.value.code == 4409  # not 4403: they ARE authorized, it's a resource guard
            assert connection_manager.has_connection(ws_session["session_id"])  # the first is untouched

        # once the first connection is gone, the student can reconnect
        with client.websocket_connect(url):
            assert connection_manager.has_connection(ws_session["session_id"])


@pytest.mark.asyncio
async def test_a_connection_that_stopped_heartbeating_is_replaced_not_a_lockout(ws_session, db_session):
    session_uuid = uuid.UUID(ws_session["session_id"])
    url = f"/ws/exam-sessions/{ws_session['session_id']}?token={ws_session['token']}"
    with TestClient(fastapi_app) as client:
        with client.websocket_connect(url) as first:
            # simulate a half-open socket: the server still holds it, but no heartbeat for minutes
            await db_session.execute(
                update(ExamSession)
                .where(ExamSession.id == session_uuid)
                .values(last_heartbeat_at=datetime.now(timezone.utc) - timedelta(minutes=5))
            )
            await db_session.commit()

            with client.websocket_connect(url) as second:
                with pytest.raises(WebSocketDisconnect) as exc_info:
                    first.receive_json()
                assert exc_info.value.code == 4408  # told it was replaced

                second.send_json({"type": "heartbeat"})
                assert second.receive_json() == {"type": "heartbeat_ack"}
            # the replaced connection's teardown must not have killed the replacement's registration mid-flight
