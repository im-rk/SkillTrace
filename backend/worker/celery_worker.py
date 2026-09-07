"""
Celery worker entrypoint.
Run with `celery -A worker.celery_worker worker`.
"""
from app.core.celery_app import celery_app

# Expose celery_app as `app` for Celery CLI convenience
app = celery_app

if __name__ == "__main__":
    celery_app.start()