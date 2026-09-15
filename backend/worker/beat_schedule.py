"""
Celery beat periodic tasks schedule (e.g., auto-submit exams past end_time).
"""
from app.core.config import settings

# Celery Beat Schedule definitions
beat_schedule = {
    "flag-stale-exam-sessions": {
        "task": "live_session_gateway.flag_stale_sessions",
        # Run at roughly half the stale threshold, so a session isn't flagged
        # much later than the threshold itself implies.
        "schedule": max(settings.STALE_SESSION_THRESHOLD_SECONDS / 2, 5.0),
    },
    "sweep-pending-submissions": {
        "task": "evaluation_pipeline.sweep_pending_submissions",
        # Same reasoning as above: run at roughly half the PEL idle threshold.
        "schedule": max(settings.SUBMISSION_PEL_MIN_IDLE_MS / 1000 / 2, 5.0),
    },
    # More tasks to be configured as modules get implemented in subsequent phases
}