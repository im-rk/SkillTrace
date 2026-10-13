"""
Pydantic schemas for Question Bank.
Includes per-type content schemas (MCQContent, TrueFalseContent, TextInputContent).
"""
from typing import Literal, Union
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.modules.question_bank.models import DifficultyLevel, QuestionType


class MCQChoice(BaseModel):
    id: str
    text: str

    model_config = ConfigDict(extra="forbid")


class MCQContent(BaseModel):
    choices: list[MCQChoice] = Field(min_length=2)
    correct_choice_id: str

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def check_correct_choice_id(self) -> "MCQContent":
        valid_ids = {c.id for c in self.choices}
        if self.correct_choice_id not in valid_ids:
            raise ValueError("correct_choice_id must match one of the provided choices")
        return self


class TrueFalseContent(BaseModel):
    correct_answer: bool

    model_config = ConfigDict(extra="forbid")


class TextInputContent(BaseModel):
    correct_answer: str
    case_sensitive: bool = False

    model_config = ConfigDict(extra="forbid")


class QuestionBase(BaseModel):
    skill_id: UUID
    question_type: Literal["multiple_choice", "true_false", "text_input"]
    prompt: str
    difficulty: Literal["easy", "medium", "hard"]
    content: Union[MCQContent, TrueFalseContent, TextInputContent]
    tags: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_content_matches_type(self) -> "QuestionBase":
        expected = {
            "multiple_choice": MCQContent,
            "true_false": TrueFalseContent,
            "text_input": TextInputContent,
        }[self.question_type]
        if not isinstance(self.content, expected):
            raise ValueError(
                f"content shape does not match question_type '{self.question_type}'"
            )
        return self


class QuestionCreate(QuestionBase):
    pass


class QuestionUpdate(BaseModel):
    prompt: str | None = None
    difficulty: Literal["easy", "medium", "hard"] | None = None
    content: Union[MCQContent, TrueFalseContent, TextInputContent] | None = None
    tags: list[str] | None = None


class QuestionResponse(BaseModel):
    id: UUID
    skill_id: UUID
    question_type: QuestionType
    prompt: str
    difficulty: DifficultyLevel
    content: dict
    version: int
    tags: list[str] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class TagResponse(BaseModel):
    id: UUID
    name: str

    model_config = ConfigDict(from_attributes=True)


class BulkImportRowResult(BaseModel):
    row_number: int
    status: Literal["success", "failed"]
    question_id: UUID | None = None
    error: str | None = None


class BulkImportResponse(BaseModel):
    total_rows: int
    succeeded: int
    failed: int
    results: list[BulkImportRowResult]


class BulkImportRequest(BaseModel):
    skill_id: UUID
    rows: list[dict]


class GenerateQuestionsRequest(BaseModel):
    skill_id: UUID
    count: int = Field(default=5, ge=1, le=10)
    difficulty: Literal["easy", "medium", "hard", "mixed"] = "mixed"
    topic: str | None = Field(default=None, max_length=200)


class GenerateQuestionsResponse(BaseModel):
    """Drafts only -- nothing is saved. The instructor reviews them and saves the ones they trust."""
    drafts: list[QuestionCreate]
    discarded: int  # model output that failed validation
