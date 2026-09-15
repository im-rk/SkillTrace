"""
Business logic for Results: student/instructor result lookups and the
audit-trail reconstruction that merges responses + session_events.
"""
from uuid import UUID
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.iam.models import UserRole
from app.modules.live_session_gateway import repository as gateway_repository
from app.modules.quiz_engine import repository as quiz_repository
from app.modules.results import repository
from app.modules.results.schemas import AuditEvent, ExamOverviewResponse, ExamResultRow, StudentExamResult


def _score_fields(row) -> tuple[float, float | None]:
    total_score = float(row.total_score or 0)
    final_mastery = float(row.average_mastery) if row.average_mastery is not None else None
    return total_score, final_mastery


def _to_student_result(row) -> StudentExamResult:
    total_score, final_mastery = _score_fields(row)
    return StudentExamResult(
        exam_id=row.exam_id,
        questions_answered=row.questions_answered,
        total_score=total_score,
        final_mastery=final_mastery,
    )


async def get_exam_result(
    session: AsyncSession, exam_id: UUID, requester_id: UUID, requester_role: UserRole, student_id: UUID | None
) -> StudentExamResult:
    target_student_id = student_id or requester_id
    if target_student_id != requester_id and requester_role not in (UserRole.instructor, UserRole.admin):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot view another student's results")

    row = await repository.get_exam_result_for_student(session, exam_id, target_student_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No results found for this exam")
    return _to_student_result(row)


async def get_exam_overview(session: AsyncSession, exam_id: UUID) -> ExamOverviewResponse:
    rows = await repository.list_exam_results(session, exam_id)
    results = []
    for row in rows:
        total_score, final_mastery = _score_fields(row)
        results.append(
            ExamResultRow(
                user_id=row.student_id, display_name=row.student_name, total_score=total_score, final_mastery=final_mastery
            )
        )
    return ExamOverviewResponse(exam_id=exam_id, results=results)


async def get_session_audit_trail(session: AsyncSession, exam_session_id: UUID) -> list[AuditEvent]:
    responses = await quiz_repository.list_responses_for_exam_session(session, exam_session_id)
    events = await gateway_repository.list_events(session, exam_session_id)

    combined = [
        AuditEvent(
            timestamp=r.answered_at,
            type="answer_submitted",
            detail={"question_id": str(r.question_id), "correct": r.is_correct},
        )
        for r in responses
    ] + [
        AuditEvent(timestamp=e.occurred_at, type=e.event_type.value, detail=e.metadata_ or {})
        for e in events
    ]
    return sorted(combined, key=lambda e: e.timestamp)
