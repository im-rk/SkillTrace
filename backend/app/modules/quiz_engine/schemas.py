"""
Pydantic schemas for Quiz Engine.
"""
from datetime import datetime
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field



def _optional_probability():
    return Field(default=None, ge=0.0, le=1.0)


class SkillCreate(BaseModel):
    name: str
    slug: str
    description: str | None = None


class SkillUpdate(BaseModel):
    """PATCH semantics: only the fields sent are changed. Slug is immutable (it is a URL/identity key)."""
    name: str | None = Field(default=None, min_length=1, max_length=150)
    description: str | None = None
    p_l0: float | None = _optional_probability()
    p_t: float | None = _optional_probability()
    p_g: float | None = _optional_probability()
    p_s: float | None = _optional_probability()
    mastery_threshold: float | None = _optional_probability()


class SkillResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    description: str | None
    p_l0: float
    p_t: float
    p_g: float
    p_s: float
    mastery_threshold: float

    model_config = ConfigDict(from_attributes=True)


class SkillReadiness(BaseModel):
    """A skill can only serve a full adaptive quiz if every difficulty tier has a question."""
    skill_id: UUID
    counts: dict[str, int]
    ready: bool
    missing_tiers: list[str]


class StudentMasteryRow(BaseModel):
    """One student's standing on a skill (admin overview)."""
    student_id: UUID
    display_name: str
    email: str
    current_mastery: float
    total_attempts: int
    is_mastered: bool
    last_updated_at: datetime


class SkillMastery(BaseModel):
    """The caller's standing on one skill (practice picker)."""
    skill_id: UUID
    name: str
    slug: str
    description: str | None
    mastery_threshold: float
    question_count: int
    current_mastery: float | None  # None = never attempted
    total_attempts: int
    is_mastered: bool


# --- free-practice quiz -----------------------------------------------------

class QuizSessionCreate(BaseModel):
    skill_id: UUID


class QuizSessionResponse(BaseModel):
    id: UUID
    skill_id: UUID
    status: Literal["in_progress", "mastered", "abandoned"]
    initial_mastery: float
    current_mastery: float
    final_mastery: float | None
    mastery_threshold: float
    questions_answered: int
    questions_correct: int
    started_at: datetime
    ended_at: datetime | None


class PracticeQuestion(BaseModel):
    """A question as a student sees it: never includes the correct answer."""
    id: UUID
    question_type: str
    prompt: str
    difficulty: str
    content: dict


class NextQuestionResponse(BaseModel):
    """`in_progress` carries a question. `mastered` / `exhausted` end the session (no question)."""
    status: Literal["in_progress", "mastered", "exhausted"]
    mastery: float
    question: PracticeQuestion | None


class AnswerCreate(BaseModel):
    question_id: UUID
    submitted_answer: str


class AnswerResponse(BaseModel):
    is_correct: bool
    mastery_before: float
    mastery_after: float
    session_status: Literal["in_progress", "mastered", "abandoned"]


# --- progress ---------------------------------------------------------------

class ProgressPoint(BaseModel):
    answered_at: datetime
    mastery_before: float
    mastery_after: float
    is_correct: bool
    source: Literal["practice", "exam"]


class ProgressResponse(BaseModel):
    skill_id: UUID
    skill_name: str
    initial_mastery: float
    mastery_threshold: float
    current_mastery: float | None
    points: list[ProgressPoint]
