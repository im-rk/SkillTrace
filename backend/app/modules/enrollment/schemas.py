"""
Pydantic schemas for Enrollment.
"""
from datetime import datetime
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field

from app.modules.scheduling.phase import ExamPhase


class EnrollRequest(BaseModel):
    student_id: UUID


class EnrollmentResponse(BaseModel):
    exam_id: UUID
    student_id: UUID
    enrolled_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AccessCodeCreate(BaseModel):
    max_uses: int | None = Field(default=None, gt=0)
    expires_at: datetime | None = None


class AccessCodeResponse(BaseModel):
    code: str
    exam_id: UUID
    max_uses: int | None
    times_used: int
    expires_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class RedeemResult(BaseModel):
    enrolled: bool
    exam_id: UUID
    access_method: Literal["manual", "access_code"]


class EnrolledStudent(BaseModel):
    student_id: UUID
    display_name: str
    email: str
    enrolled_at: datetime


class MyExam(BaseModel):
    exam_id: UUID
    title: str
    description: str | None
    start_time: datetime
    end_time: datetime
    duration_minutes: int
    phase: ExamPhase
    session_id: UUID | None
    session_status: str | None
