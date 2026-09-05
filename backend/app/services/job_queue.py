"""Database-owned lifecycle for retryable background work."""

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.interview import (
    ProcessingJob,
    ProcessingJobKind,
    ProcessingJobStatus,
)


class DurableJobService:
    def __init__(self, db: Session, *, max_attempts: int = 3) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be positive")
        self.db = db
        self.max_attempts = max_attempts

    def create_once(
        self,
        kind: ProcessingJobKind,
        entity_id: UUID,
        idempotency_key: str,
        *,
        available_at: datetime | None = None,
    ) -> ProcessingJob:
        key = idempotency_key.strip()
        if not key or len(key) > 180:
            raise ValueError("idempotency_key must contain 1..180 characters")
        existing = self.db.scalar(
            select(ProcessingJob).where(ProcessingJob.idempotency_key == key)
        )
        if existing:
            return existing
        job = ProcessingJob(
            kind=kind,
            entity_id=entity_id,
            idempotency_key=key,
            status=ProcessingJobStatus.PENDING,
            attempt_count=0,
            available_at=available_at or datetime.now(timezone.utc),
        )
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        return job

    def start(self, job: ProcessingJob) -> bool:
        if job.status not in {
            ProcessingJobStatus.PENDING,
            ProcessingJobStatus.RETRYABLE_FAILED,
        } or job.attempt_count >= self.max_attempts:
            return False
        job.status = ProcessingJobStatus.RUNNING
        job.attempt_count += 1
        job.started_at = datetime.now(timezone.utc)
        job.completed_at = None
        job.last_error_code = None
        self.db.commit()
        return True

    def complete(self, job: ProcessingJob) -> None:
        job.status = ProcessingJobStatus.COMPLETED
        job.completed_at = datetime.now(timezone.utc)
        self.db.commit()

    def fail(self, job: ProcessingJob, error_code: str) -> None:
        job.last_error_code = error_code.strip()[:120] or "unknown_error"
        job.completed_at = datetime.now(timezone.utc)
        job.status = (
            ProcessingJobStatus.TERMINAL_FAILED
            if job.attempt_count >= self.max_attempts
            else ProcessingJobStatus.RETRYABLE_FAILED
        )
        self.db.commit()

    def recover_stale(self, older_than: timedelta) -> int:
        cutoff = datetime.now(timezone.utc) - older_than
        jobs = list(
            self.db.scalars(
                select(ProcessingJob).where(
                    ProcessingJob.status == ProcessingJobStatus.RUNNING,
                    ProcessingJob.started_at < cutoff,
                )
            )
        )
        for job in jobs:
            job.status = (
                ProcessingJobStatus.TERMINAL_FAILED
                if job.attempt_count >= self.max_attempts
                else ProcessingJobStatus.RETRYABLE_FAILED
            )
            job.last_error_code = "worker_lost"
            job.completed_at = datetime.now(timezone.utc)
        self.db.commit()
        return len(jobs)
