"""
Celery application instance and baseline configuration.
"""
from celery import Celery
from celery.signals import setup_logging
from app.core.config import settings
from app.core.logging import configure_logging
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


@setup_logging.connect
def _configure_worker_logging(**_kwargs) -> None:
    # Connecting to this signal stops Celery installing its own log format, so worker
    # lines carry the same request-id field, formatted identically, as the API's.
    configure_logging()


@celery_app.task(name="tasks.ping")
def ping() -> str:
    """
    Trivial task to verify Celery broker and worker connectivity.
    """
    return "pong"
