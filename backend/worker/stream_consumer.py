"""
Entrypoint: `python -m worker.stream_consumer`.

A long-running process, separate from the FastAPI app and separate from the
Celery workers -- reads submission_queue_log entries off Redis Stream
stream:submissions and dispatches a Celery task per entry. See
app/modules/evaluation_pipeline/stream_consumer.py for the actual loop.
"""
import asyncio
from app.core.redis_client import get_redis
from app.modules.evaluation_pipeline.stream_consumer import consume_submissions_loop

if __name__ == "__main__":
    asyncio.run(consume_submissions_loop(get_redis()))
