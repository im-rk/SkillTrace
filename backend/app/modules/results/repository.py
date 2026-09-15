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
