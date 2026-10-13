"""
Pydantic schemas for Scheduling.
"""
from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.modules.scheduling.models import ExamStatus
from app.modules.scheduling.phase import ExamPhase, exam_phase


class ExamCreate(BaseModel):
    title: str
    description: str | None = None
    skill_id: UUID
    start_time: datetime
    end_time: datetime
    duration_minutes: int = Field(gt=0)


class ExamResponse(BaseModel):
    id: UUID
    title: str
    description: str | None
    skill_id: UUID
    start_time: datetime
    end_time: datetime
    duration_minutes: int
    status: ExamStatus

    model_config = ConfigDict(from_attributes=True)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def phase(self) -> ExamPhase:
        return exam_phase(self.status, self.start_time, self.end_time)


class ExamListItem(ExamResponse):
    """An exam in the instructor's list, with what they need to see at a glance."""
    skill_name: str
    question_count: int
    enrolled_count: int


class AssignedQuestionResponse(BaseModel):
    """A question as assigned to an exam -- instructor view (a student never gets this)."""
    question_id: UUID
    prompt: str
    question_type: str
    difficulty: str
    display_order: int
    points: Decimal


class ExamQuestionAssign(BaseModel):
    question_id: UUID
    display_order: int
    points: Decimal = Decimal("1.0")


class AssignQuestionsRequest(BaseModel):
    questions: list[ExamQuestionAssign]


class ExamSessionResponse(BaseModel):
    session_id: UUID
    exam_id: UUID
    status: Literal["in_progress", "paused_disconnected", "submitted", "auto_submitted", "expired"]
    started_at: datetime


class StudentExamQuestion(BaseModel):
    question_id: UUID
    prompt: str
    question_type: Literal["multiple_choice", "true_false", "text_input"]
    difficulty: Literal["easy", "medium", "hard"]
    display_order: int
    points: Decimal
    # Sanitized: never includes the correct answer (see question_bank.service.strip_correct_answer).
    content: dict


class StudentExamView(BaseModel):
    exam_id: UUID
    title: str
    description: str | None
    duration_minutes: int
    questions: list[StudentExamQuestion]
