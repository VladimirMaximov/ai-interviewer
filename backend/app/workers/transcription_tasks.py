"""Durable CPU-worker entrypoints for transcription and runtime evaluation."""

from functools import lru_cache
from uuid import UUID

import boto3
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.adapters.storage import S3ObjectStorage
from app.config import settings
from app.database import presenter_dispatcher_factory, transcription_provider_factory
from app.services.audio_processing import WhisperAudioProcessor
from app.services.runtime_evaluation import RuntimeEvaluationService
from app.services.transcription_scheduler import TranscriptionScheduler
from app.workers.celery_app import celery_app


@lru_cache(maxsize=1)
def _scheduler() -> TranscriptionScheduler:
    engine = create_engine(settings.database_url, pool_pre_ping=True)
    sessions = sessionmaker(engine, expire_on_commit=False)
    client = boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
    )
    storage = S3ObjectStorage(client, settings.s3_bucket)
    processor = WhisperAudioProcessor(
        transcription_provider_factory(), settings.ffmpeg_binary
    )
    runtime_evaluation = RuntimeEvaluationService(
        sessions,
        presenter_dispatcher=presenter_dispatcher_factory(),
    )
    return TranscriptionScheduler(
        sessions, storage, processor, runtime_evaluation
    )


@celery_app.task(
    name="app.workers.transcription_tasks.transcribe_response",
    autoretry_for=(RuntimeError,), retry_backoff=True, max_retries=2,
)
def transcribe_response(response_id: str, key: str) -> None:
    _scheduler()._run(UUID(response_id), key)


@celery_app.task(name="app.workers.transcription_tasks.transcribe_segment")
def transcribe_segment(
    response_id: str, key: str, start_offset_ms: int, end_offset_ms: int
) -> None:
    _scheduler()._run_segment(
        UUID(response_id), key, start_offset_ms, end_offset_ms
    )


@celery_app.task(
    name="app.workers.transcription_tasks.transcribe_chunk_segment",
    acks_late=True,
    reject_on_worker_lost=True,
)
def transcribe_chunk_segment(
    response_id: str,
    chunks: list[list[str | int]],
    start_offset_ms: int,
    end_offset_ms: int,
) -> None:
    _scheduler()._run_chunk_segment(
        UUID(response_id), chunks, start_offset_ms, end_offset_ms
    )


@celery_app.task(name="app.workers.transcription_tasks.evaluate_response")
def evaluate_response(response_id: str) -> None:
    scheduler = _scheduler()
    if scheduler.runtime_evaluation:
        scheduler.runtime_evaluation.evaluate_completed_response(UUID(response_id))
