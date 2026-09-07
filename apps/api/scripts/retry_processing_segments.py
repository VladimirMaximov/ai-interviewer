"""Retry interrupted recording-segment transcriptions from durable media chunks."""

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import workflow_factory
from app.models.interview import (
    CandidateResponse,
    InterviewRecording,
    InterviewRecordingChunk,
    TranscriptionStatus,
)


engine = create_engine(settings.database_url)
workflow = workflow_factory()
scheduler = workflow.scheduler

with Session(engine) as db:
    composed_recordings = set()
    responses = db.scalars(
        select(CandidateResponse).where(
            CandidateResponse.transcription_status.in_(
                [TranscriptionStatus.PROCESSING, TranscriptionStatus.FAILED]
            )
        )
    ).all()
    for response in responses:
        recording = db.scalar(
            select(InterviewRecording).where(
                InterviewRecording.session_id == response.session_id
            )
        )
        chunks = list(
            db.scalars(
                select(InterviewRecordingChunk)
                .where(
                    InterviewRecordingChunk.recording_id == recording.id,
                    InterviewRecordingChunk.uploaded_at.is_not(None),
                )
                .order_by(InterviewRecordingChunk.sequence)
            )
        ) if recording else []
        if not chunks or response.start_offset_ms is None or response.end_offset_ms is None:
            continue
        if recording.id not in composed_recordings:
            workflow._compose_recording(recording, chunks)
            composed_recordings.add(recording.id)
        response.transcription_status = TranscriptionStatus.PROCESSING
        db.commit()
        scheduler.schedule_segment_chunks(
            response.id,
            [(item.storage_key, item.start_offset_ms, item.end_offset_ms) for item in chunks],
            response.start_offset_ms,
            response.end_offset_ms,
        )
    print(f"Queued {len(responses)} processing responses")
