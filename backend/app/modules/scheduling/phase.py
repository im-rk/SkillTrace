"""
Derived, time-based exam phase. Exam.status only ever records the explicit
transition to `closed`; whether an exam is upcoming / live / ended is a pure
function of the clock, so it is computed rather than stored (nothing would
keep a stored value fresh).
"""
from datetime import datetime, timezone
from typing import Literal

from app.modules.scheduling.models import ExamStatus

ExamPhase = Literal["upcoming", "live", "ended", "closed"]


def exam_phase(status: ExamStatus, start_time: datetime, end_time: datetime, now: datetime | None = None) -> ExamPhase:
    if status == ExamStatus.closed:
        return "closed"
    now = now or datetime.now(timezone.utc)
    if now < start_time:
        return "upcoming"
    return "live" if now <= end_time else "ended"
