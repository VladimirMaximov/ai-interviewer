"""Celery configuration with isolated CPU and serialized GPU queues."""

from app.config import settings

try:
    from celery import Celery
    from kombu import Queue
except ImportError as error:  # pragma: no cover - optional worker extra
    raise RuntimeError(
        "Install the backend 'workers' extra before starting a worker"
    ) from error


celery_app = Celery(
    "ai_interviewer",
    broker=settings.redis_url,
    include=[
        "app.workers.presenter_tasks",
        "app.workers.transcription_tasks",
    ],
)
celery_app.conf.update(
    broker_connection_retry_on_startup=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_default_queue=settings.celery_cpu_queue,
    task_queues=(
        Queue(settings.celery_cpu_queue),
        Queue(settings.celery_gpu_queue),
    ),
    task_routes={
        "app.workers.presenter_tasks.*": {"queue": settings.celery_gpu_queue},
        "app.workers.transcription_tasks.*": {"queue": settings.celery_cpu_queue},
    },
)
