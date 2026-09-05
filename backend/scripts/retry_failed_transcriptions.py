"""Reschedule failed synthetic local responses after repairing ASR dependencies."""
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from app.config import settings
from app.database import workflow_factory
from app.services.audio_processing import WhisperAudioProcessor
from app.database import transcription_provider_factory
from pathlib import Path
import tempfile
from app.models.interview import CandidateResponse, TranscriptionStatus

engine = create_engine(settings.database_url)
workflow = workflow_factory()
processor = WhisperAudioProcessor(transcription_provider_factory(), settings.ffmpeg_binary)
with Session(engine) as db:
    failed = db.scalars(select(CandidateResponse).where(CandidateResponse.transcription_status == TranscriptionStatus.FAILED)).all()
    for response in failed:
        try:
            with tempfile.TemporaryDirectory() as directory:
                source = Path(directory) / "response.webm"
                workflow.storage.download_to(response.storage_key, source)
                response.transcript_text = processor.transcribe(source)
            response.transcription_status = TranscriptionStatus.COMPLETED
        except Exception as error:
            response.transcription_status = TranscriptionStatus.FAILED
            print(f"{response.id}: {error}")
    db.commit()
print(f"Rescheduled {len(failed)} responses")
