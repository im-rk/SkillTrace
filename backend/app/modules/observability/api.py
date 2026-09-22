"""
GET /admin/metrics -- a deliberately lightweight, JSON-only operational snapshot.

This is an MVP-appropriate choice, not the production answer: at real scale
these numbers would be exported to Prometheus (scraped, graphed in Grafana,
alerted on) or a hosted APM instead of being polled by hand. Naming that as a
deliberate deferral is the point -- a four-number endpoint answers "is the
pipeline backing up right now?" without standing up a metrics stack.
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.session import get_db
from app.core.redis_client import get_redis
from app.modules.evaluation_pipeline.models import SubmissionStatus
from app.modules.evaluation_pipeline.repository import count_submissions_by_status
from app.modules.iam.deps import require_admin
from app.modules.iam.schemas import TokenData
from app.modules.live_session_gateway.websocket_manager import connection_manager
from app.modules.scheduling.locking import count_lock_contention_last_hour

router = APIRouter(tags=["observability"])


class SystemMetrics(BaseModel):
    queue_depth_queued: int
    queue_depth_processing: int
    # Connections held by THIS API process (the manager is per-process; multi-instance
    # deployments would sum across instances).
    active_websocket_connections: int
    lock_contention_last_hour: int


@router.get("/admin/metrics", response_model=SystemMetrics)
async def get_metrics(
    session: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(require_admin),
) -> SystemMetrics:
    return SystemMetrics(
        queue_depth_queued=await count_submissions_by_status(session, SubmissionStatus.pending),
        queue_depth_processing=await count_submissions_by_status(session, SubmissionStatus.processing),
        active_websocket_connections=connection_manager.total_connection_count(),
        lock_contention_last_hour=await count_lock_contention_last_hour(get_redis()),
    )
