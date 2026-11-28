"""Celery application. Start a worker with:

    celery -A app.worker worker --loglevel=info

Redis only carries the messages. Job state and results live in the database, so
the API can report on a job without asking Celery.
"""

from celery import Celery

from app.config import settings

celery_app = Celery("tender_assistant", broker=settings.redis_url, include=["app.jobs.tasks"])
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    task_ignore_result=True,
    # A job is acknowledged only after it finishes, so a worker crash requeues it.
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    # OCR is slow and CPU bound; one job per worker process at a time.
    worker_prefetch_multiplier=1,
    task_always_eager=settings.celery_eager,
    broker_connection_retry_on_startup=True,
)
