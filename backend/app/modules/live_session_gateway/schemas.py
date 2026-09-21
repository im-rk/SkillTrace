"""
Pydantic schemas for Live Session Gateway.
"""
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel


class SessionTimingResponse(BaseModel):
    elapsed_active_seconds: int
    total_duration_seconds: int
    status: str


class SessionSubmittedResponse(BaseModel):
    session_id: UUID
    status: str
    completed_at: datetime | None
