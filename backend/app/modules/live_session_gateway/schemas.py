"""
Pydantic schemas for Live Session Gateway.
"""
from pydantic import BaseModel


class SessionTimingResponse(BaseModel):
    elapsed_active_seconds: int
    total_duration_seconds: int
    status: str
