"""
Pydantic schemas for Evaluation Pipeline.
Includes SubmissionPayload.
"""
from typing import Literal
from uuid import UUID
from pydantic import BaseModel


class SubmissionPayload(BaseModel):
    question_id: UUID
    answer: str


class SubmissionAcceptedResponse(BaseModel):
    status: Literal["accepted"] = "accepted"
    log_id: UUID


class SubmissionStatusResponse(BaseModel):
    log_id: UUID
    status: Literal["pending", "processing", "completed", "failed"]
