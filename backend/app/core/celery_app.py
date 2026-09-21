"""
Celery application instance and baseline configuration.
"""
from celery import Celery
from app.core.config import settings
from worker.beat_schedule import beat_schedule

celery_app = Celery(
    "skilltrace",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.modules.live_session_gateway.tasks",
        "app.modules.evaluation_pipeline.tasks",
        "app.modules.scheduling.tasks",
        "app.modules.results.tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    beat_schedule=beat_schedule,
    # Ack after completion, and requeue if the worker process dies mid-task; without
    # this a SIGKILLed worker silently loses the task it was running (docs/adr/0008).
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
)


@celery_app.task(name="tasks.ping")
def ping() -> str:
    """
    Trivial task to verify Celery broker and worker connectivity.
    """
    return "pong"
