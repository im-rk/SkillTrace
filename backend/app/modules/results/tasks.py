"""
Celery task wrapping the mv_exam_results refresh. Dispatched (not called
inline) from scheduling.service.close_exam because a refresh over a large
results set could take longer than is reasonable to hold up that request.
"""
from app.core.async_task import run_async
from app.core.celery_app import celery_app
from app.core.db.session import async_session_maker
from app.modules.results.refresh_service import refresh_exam_results


async def _refresh() -> None:
    async with async_session_maker() as session:
        await refresh_exam_results(session)


@celery_app.task(name="results.refresh_exam_results")
def refresh_exam_results_task(exam_id: str) -> None:
    run_async(_refresh())
