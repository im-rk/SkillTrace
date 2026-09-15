"""
Celery task: periodic sweep for stale (heartbeat-missing) exam sessions.
"""
from app.core.async_task import run_async
from app.core.celery_app import celery_app
from app.core.db.session import async_session_maker
from app.modules.live_session_gateway import service


async def _flag_stale_sessions() -> int:
    async with async_session_maker() as session:
        return await service.flag_stale_sessions(session)


@celery_app.task(name="live_session_gateway.flag_stale_sessions")
def flag_stale_sessions() -> int:
    return run_async(_flag_stale_sessions())
