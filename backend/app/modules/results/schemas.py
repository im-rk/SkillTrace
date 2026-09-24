"""
Pydantic schemas for Results.
"""
from datetime import datetime
from typing import Any
from uuid import UUID
from pydantic import BaseModel


class StudentExamResult(BaseModel):
    exam_id: UUID
    questions_answered: int
    total_score: float
    final_mastery: float | None


class ExamResultRow(BaseModel):
    user_id: UUID
    display_name: str
    total_score: float
    final_mastery: float | None


class ExamOverviewResponse(BaseModel):
    exam_id: UUID
    results: list[ExamResultRow]


class AuditEvent(BaseModel):
    timestamp: datetime
    type: str
    detail: dict[str, Any]


class AuditTrailResponse(BaseModel):
    session_id: UUID
    events: list[AuditEvent]


class ItemAnalysisRow(BaseModel):
    question_id: UUID
    prompt: str
    sample_size: int
    # None means "not enough data" (see item_analysis.py's thresholds), not zero.
    p_value: float | None
    discrimination: float | None


class ItemAnalysisResponse(BaseModel):
    exam_id: UUID
    items: list[ItemAnalysisRow]
