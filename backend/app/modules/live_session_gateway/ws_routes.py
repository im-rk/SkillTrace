"""
The WebSocket endpoint for a live exam session.

The load-bearing property of this file: verify_exam_access_ws is resolved and
checked BEFORE websocket.accept() is ever called (see docs/adr/0010). A
rejected connection is closed, not accepted-then-closed -- accept() must have
a zero call count for every rejection path, which is what
tests/integration/enrollment/test_access_control_ws.py's pre-accept test
(and this module's own WS integration test) assert directly.
"""
from datetime import datetime, timezone
from uuid import UUID
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.session import get_db
from app.modules.enrollment.deps import verify_exam_access_ws
from app.modules.live_session_gateway import service as session_service
from app.modules.live_session_gateway.websocket_manager import connection_manager

router = APIRouter()


@router.websocket("/ws/exam-sessions/{session_id}")
async def exam_session_ws(websocket: WebSocket, session_id: str, db: AsyncSession = Depends(get_db)):
    try:
        session_uuid = UUID(session_id)
    except ValueError:
        await websocket.close(code=4404)
        return

    exam_id = await session_service.resolve_exam_id_for_session(db, session_uuid)
    if exam_id is None:
        await websocket.close(code=4404)
        return

    user = await verify_exam_access_ws(websocket, exam_id, db)
    if user is None:
        await websocket.close(code=4403)
        return  # accept() NEVER called for a rejected connection

    await websocket.accept()
    await connection_manager.connect(session_id, str(exam_id), websocket)
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
        await connection_manager.disconnect(session_id, str(exam_id))
        await session_service.pause_session(db, session_uuid, datetime.now(timezone.utc))
