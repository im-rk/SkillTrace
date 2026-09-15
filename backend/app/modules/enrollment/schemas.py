"""
Pydantic schemas for Enrollment.
"""
from datetime import datetime
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


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
