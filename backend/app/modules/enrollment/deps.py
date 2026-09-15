"""
FastAPI dependencies for Enrollment.
Includes verify_exam_access (REST) + verify_exam_access_ws (WebSocket).
"""
from uuid import UUID
from fastapi import Depends, HTTPException, WebSocket, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.session import get_db
from app.modules.iam.deps import get_current_user
from app.modules.iam.schemas import TokenData
from app.modules.iam.service import decode_access_token
from app.modules.enrollment import repository


async def check_enrollment(session: AsyncSession, user_id: UUID, exam_id: UUID) -> bool:
    """Shared core logic -- no HTTP or WebSocket concepts here."""
    enrollment = await repository.get_enrollment(session, exam_id, user_id)
    return enrollment is not None


async def verify_exam_access(
    exam_id: UUID,
    current_user: TokenData = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> TokenData:
    """REST dependency. Used as a route parameter, so FastAPI resolves it before
    the route body runs -- an unenrolled request 403s here and the route handler
    (and any further data it would fetch) never executes."""
    if not await check_enrollment(session, current_user.id, exam_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enrolled in this exam")
    return current_user


async def verify_exam_access_ws(websocket: WebSocket, exam_id: UUID, session: AsyncSession) -> TokenData | None:
    """WebSocket handshakes don't share HTTP's exception-based signaling, so this
    returns None on every failure mode (no token, malformed/expired token,
    valid token but unenrolled) instead of raising. The caller is responsible
    for closing the connection on None, before accepting it."""
    token = websocket.query_params.get("token")
    if not token:
        return None
    try:
        current_user = decode_access_token(token)
    except Exception:
        return None
    if not await check_enrollment(session, current_user.id, exam_id):
        return None
    return current_user
