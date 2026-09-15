"""
REST API routes for Live Session Gateway (the WebSocket route lives in
ws_routes.py). Includes GET /exam-sessions/{id}/timing, backing the
frontend's server-authoritative timer resync.
"""
from uuid import UUID
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.session import get_db
from app.modules.iam.deps import get_current_user
from app.modules.iam.schemas import TokenData
from app.modules.live_session_gateway import service
from app.modules.live_session_gateway.schemas import SessionTimingResponse

router = APIRouter(tags=["live-session-gateway"])


@router.get("/exam-sessions/{session_id}/timing", response_model=SessionTimingResponse)
async def get_session_timing(
    session_id: UUID,
    session: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
):
    return await service.get_session_timing(session, session_id, current_user.id)
