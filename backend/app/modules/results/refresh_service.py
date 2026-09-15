"""
Service to refresh mv_exam_results (called by a Celery task on exam close).

CONCURRENTLY specifically: a plain REFRESH takes an exclusive lock on the view
for the duration of the refresh, blocking every read -- exactly the moment
students are most likely to be checking results. CONCURRENTLY keeps reads
serving the pre-refresh snapshot instead, at the cost of requiring the unique
index the initial migration already created on (exam_id, student_id).
"""
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def refresh_exam_results(session: AsyncSession) -> None:
    await session.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY mv_exam_results"))
    await session.commit()
