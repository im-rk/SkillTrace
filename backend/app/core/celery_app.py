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
    # Without these, Celery's default is to ack a task the moment a worker
    # *receives* it, not after it finishes -- a worker killed mid-task (SIGKILL,
    # OOM, container restart) loses that task silently, with nothing left in
    # the broker to redeliver it. That's a real gap Phase 12's chaos testing
    # (killing the worker mid-run) actually exercises: a submission whose
    # process_submission task was killed mid-execution would otherwise stay at
    # status='processing' forever, since neither the Redis-Streams PEL sweep
    # (evaluation_pipeline.stream_consumer's own recovery mechanism) nor
    # anything else revisits it once the stream message is XACKed.
    # task_acks_late + task_reject_on_worker_lost: the message is only acked
    # after the task completes, and is explicitly requeued if the worker
    # process is lost while running it -- Celery itself now redelivers, and
    # Phase 9's idempotency guard (status == completed -> no-op) makes
    # reprocessing safe.
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
