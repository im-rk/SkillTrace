"""
The WebSocket endpoint for a live exam session.

The load-bearing property of this file: verify_exam_access_ws is resolved and
checked BEFORE websocket.accept() is ever called (see docs/adr/0010). A
rejected connection is closed, not accepted-then-closed -- accept() must have
a zero call count for every rejection path, which is what
tests/integration/enrollment/test_access_control_ws.py's pre-accept test
(and this module's own WS integration test) assert directly.
"""
from contextlib import suppress
from datetime import datetime, timedelta, timezone
from uuid import UUID
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db.session import get_db
from app.modules.enrollment.deps import verify_exam_access_ws
from app.modules.live_session_gateway import repository as session_repository
from app.modules.live_session_gateway import service as session_service
from app.modules.live_session_gateway.websocket_manager import connection_manager

router = APIRouter()

# Distinct from 4403 (not authorized -- never retry): these are about resource use, and a client
# that gets 4409 may retry, because the connection holding the session might be a dead one.
WS_CLOSE_REPLACED = 4408  # sent to an old connection when a newer one takes over the session
WS_CLOSE_ALREADY_CONNECTED = 4409  # sent to a second live connection for the same session


def _heartbeat_is_stale(exam_session) -> bool:
    age = datetime.now(timezone.utc) - exam_session.last_heartbeat_at
    return age > timedelta(seconds=settings.STALE_SESSION_THRESHOLD_SECONDS)


@router.websocket("/ws/exam-sessions/{session_id}")
async def exam_session_ws(websocket: WebSocket, session_id: str, db: AsyncSession = Depends(get_db)):
    try:
        session_uuid = UUID(session_id)
    except ValueError:
        await websocket.close(code=4404)
        return

    exam_session = await session_repository.get_session(db, session_uuid)
    if exam_session is None:
        await websocket.close(code=4404)
        return
    exam_id = exam_session.exam_id

    user = await verify_exam_access_ws(websocket, exam_id, db)
    # Enrolled in the exam is not enough: the session itself must be theirs, or
    # any enrolled student could heartbeat/pause/observe another student's session.
    if user is None or exam_session.student_id != user.id:
        await websocket.close(code=4403)
        return  # accept() NEVER called for a rejected connection

    # One live connection per session: a resource-abuse guard, not a security one (the caller is
    # already authorized above). A connection that has stopped heartbeating is presumed dead --
    # e.g. a half-open TCP socket after a network drop -- and is replaced rather than locking the
    # student out of their own exam.
    if connection_manager.has_connection(session_id) and not _heartbeat_is_stale(exam_session):
        await websocket.close(code=WS_CLOSE_ALREADY_CONNECTED)
        return

    await websocket.accept()
    previous = await connection_manager.connect(session_id, str(exam_id), websocket)
    if previous is not None:
        with suppress(Exception):  # it is presumed dead; failing to say goodbye is fine
            await previous.close(code=WS_CLOSE_REPLACED)
    if exam_session.status in session_repository.ACTIVE_STATUSES:
        # Being connected is the heartbeat: resumes a paused session right away
        # instead of waiting for the client's first periodic heartbeat.
        await session_service.update_heartbeat(db, session_uuid)
    if exam_session.status not in session_repository.ACTIVE_STATUSES:
        # Connecting to an already-ended session: converge the client immediately.
        await websocket.send_json(
            {"type": "time_up", "exam_id": str(exam_id), "session_id": session_id, "status": exam_session.status.value}
        )
    try:
        while True:
            data = await websocket.receive_json()
            if data.get("type") == "heartbeat":
                await session_service.update_heartbeat(db, session_uuid)
                await websocket.send_json({"type": "heartbeat_ack"})
            # "answer_submitted" is relayed to Phase 9's evaluation pipeline
            # fast path, not yet implemented -- other message types are
            # ignored rather than closing the connection.
    except WebSocketDisconnect:
        # A connection that was replaced no longer owns the session: it must not pause it.
        if await connection_manager.disconnect(session_id, str(exam_id), websocket):
            await session_service.pause_session(db, session_uuid, datetime.now(timezone.utc))
