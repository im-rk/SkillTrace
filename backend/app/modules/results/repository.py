"""
Data access repository for Results.
Reads exclusively from mv_exam_results -- never joins exam_sessions/responses
live, which is the exact per-page-load cost this materialized view exists to
avoid (see docs/adr and Phase 10 spec Section 3.4's query-plan proof test).
"""
from uuid import UUID
from sqlalchemy import Row, text
from sqlalchemy.ext.asyncio import AsyncSession

_SELECT_COLUMNS = "exam_id, student_id, student_name, questions_answered, total_score, average_mastery"


async def get_exam_result_for_student(session: AsyncSession, exam_id: UUID, student_id: UUID) -> Row | None:
    result = await session.execute(
        text(f"SELECT {_SELECT_COLUMNS} FROM mv_exam_results WHERE exam_id = :exam_id AND student_id = :student_id"),
        {"exam_id": exam_id, "student_id": student_id},
    )
    return result.first()


async def list_exam_results(session: AsyncSession, exam_id: UUID) -> list[Row]:
    result = await session.execute(
        text(f"SELECT {_SELECT_COLUMNS} FROM mv_exam_results WHERE exam_id = :exam_id ORDER BY student_name"),
        {"exam_id": exam_id},
    )
    return list(result.all())


async def list_item_analysis_rows(session: AsyncSession, exam_id: UUID) -> list[Row]:
    """One row per (question, student) who answered it, restricted to students eligible
    for this exam's results (same submitted/auto_submitted restriction mv_exam_results
    itself applies -- joining through it reuses that definition rather than repeating
    it), carrying that student's overall exam score for the top/bottom split."""
    result = await session.execute(
        text(
            "SELECT r.question_id, es.student_id, r.is_correct, mv.total_score"
            " FROM responses r"
            " JOIN exam_sessions es ON es.id = r.exam_session_id"
            " JOIN mv_exam_results mv ON mv.exam_id = es.exam_id AND mv.student_id = es.student_id"
            " WHERE es.exam_id = :exam_id"
        ),
        {"exam_id": exam_id},
    )
    return list(result.all())
