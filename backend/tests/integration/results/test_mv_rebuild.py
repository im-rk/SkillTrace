"""
Disaster recovery for mv_exam_results: a full, non-concurrent REFRESH rebuilds the
view from the underlying tables -- including when the unique index that the
day-to-day CONCURRENTLY refresh depends on is missing.
"""
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.modules.quiz_engine.models import Response
from app.modules.results import repository
from app.modules.results.refresh_service import rebuild_exam_results, refresh_exam_results


async def _add_late_response(db_session, setup) -> None:
    """A graded answer that lands after the last refresh: the view is now stale."""
    db_session.add(
        Response(
            exam_session_id=uuid.UUID(setup["exam_session_id"]),
            question_id=uuid.UUID(setup["question_id"]),
            submitted_answer="b",
            is_correct=True,
            mastery_before=0.5,
            mastery_after=0.6,
            p_t_used=0.15,
            p_g_used=0.2,
            p_s_used=0.1,
            points_awarded=Decimal("5.0"),
            answered_at=datetime.now(timezone.utc),
        )
    )
    await db_session.commit()


async def _row(db_session, setup):
    return await repository.get_exam_result_for_student(
        db_session, uuid.UUID(setup["exam_id"]), uuid.UUID(setup["student_id"])
    )


@pytest.mark.asyncio
async def test_case_6_full_rebuild_recovers_a_stale_view(db_session, graded_exam_setup):
    await refresh_exam_results(db_session)
    fresh = await _row(db_session, graded_exam_setup)
    assert (fresh.questions_answered, float(fresh.total_score)) == (1, 2.0)

    await _add_late_response(db_session, graded_exam_setup)
    stale = await _row(db_session, graded_exam_setup)
    assert (stale.questions_answered, float(stale.total_score)) == (1, 2.0), "the view should not know yet"

    await rebuild_exam_results(db_session)

    rebuilt = await _row(db_session, graded_exam_setup)
    assert (rebuilt.questions_answered, float(rebuilt.total_score)) == (2, 7.0)


@pytest.mark.asyncio
async def test_rebuild_works_when_the_concurrent_refresh_index_is_gone(db_session, graded_exam_setup):
    await refresh_exam_results(db_session)
    await _add_late_response(db_session, graded_exam_setup)

    await db_session.execute(text("DROP INDEX idx_mv_exam_results_pk"))
    await db_session.commit()
    try:
        # the routine path cannot run without its unique index...
        with pytest.raises(DBAPIError):
            await refresh_exam_results(db_session)
        await db_session.rollback()

        # ...the recovery path does not need it
        await rebuild_exam_results(db_session)
        rebuilt = await _row(db_session, graded_exam_setup)
        assert (rebuilt.questions_answered, float(rebuilt.total_score)) == (2, 7.0)
    finally:
        await db_session.rollback()
        await db_session.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_exam_results_pk ON mv_exam_results(exam_id, student_id)"))
        await db_session.commit()
