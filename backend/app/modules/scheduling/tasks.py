"""
Celery Beat task: close any exam whose end_time has passed without a manual
close, so mv_exam_results still gets refreshed even if nobody clicked "close".
"""
from app.core.async_task import run_async
from app.core.celery_app import celery_app
from app.core.db.session import async_session_maker
from app.modules.scheduling.service import auto_close_expired_exams


async def _auto_close() -> int:
    async with async_session_maker() as session:
        return await auto_close_expired_exams(session)


@celery_app.task(name="scheduling.auto_close_expired_exams")
def auto_close_expired_exams_task() -> int:
    return run_async(_auto_close())
