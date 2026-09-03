"""Request-safe background transcription with a fresh database session per job."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import shutil
from sqlalchemy.orm import sessionmaker
from app.adapters.storage import PrivateObjectStorage
from app.models.interview import CandidateResponse, TranscriptionStatus

class TranscriptionScheduler:
    def __init__(self, sessions: sessionmaker, storage: PrivateObjectStorage, processor) -> None:
        self.sessions, self.storage, self.processor = sessions, storage, processor
        self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="asr")
    def schedule(self, response_id, key: str) -> None:
        self.executor.submit(self._run, response_id, key)
    def schedule_segment(self, response_id, key: str, start_offset_ms: int, end_offset_ms: int) -> None:
        self.executor.submit(self._run_segment, response_id, key, start_offset_ms, end_offset_ms)
    def schedule_segment_chunks(self, response_id, chunks, start_offset_ms: int, end_offset_ms: int) -> None:
        self.executor.submit(self._run_chunk_segment, response_id, chunks, start_offset_ms, end_offset_ms)
    def _run(self, response_id, key: str) -> None:
        import tempfile
        try:
            with tempfile.TemporaryDirectory(prefix="ai-interviewer-job-") as directory:
                source = Path(directory) / "response.webm"; self.storage.download_to(key, source)
                transcript = self.processor.transcribe(source)
            status, text = TranscriptionStatus.COMPLETED, transcript
        except Exception:
            status, text = TranscriptionStatus.FAILED, None
        with self.sessions() as db:
            response = db.get(CandidateResponse, response_id)
            if response: response.transcription_status, response.transcript_text = status, text; db.commit()

    def _run_segment(self, response_id, key: str, start_offset_ms: int, end_offset_ms: int) -> None:
        import tempfile
        try:
            with tempfile.TemporaryDirectory(prefix="ai-interviewer-segment-") as directory:
                source = Path(directory) / "recording.webm"
                segment = Path(directory) / "segment.webm"
                self.storage.download_to(key, source)
                self.processor.extract_audio_segment(source, segment, start_offset_ms, end_offset_ms)
                transcript = self.processor.transcribe(segment)
            status, text = TranscriptionStatus.COMPLETED, transcript
        except Exception:
            status, text = TranscriptionStatus.FAILED, None
        with self.sessions() as db:
            response = db.get(CandidateResponse, response_id)
            if response:
                response.transcription_status, response.transcript_text = status, text
                db.commit()

    def _run_chunk_segment(self, response_id, chunks, start_offset_ms: int, end_offset_ms: int) -> None:
        """Build a temporary byte stream from uploaded chunks and transcribe one interval.

        This keeps only transient files on the worker; original video chunks remain
        private objects and are never copied into PostgreSQL or the repository.
        """
        import tempfile
        try:
            with tempfile.TemporaryDirectory(prefix="ai-interviewer-chunk-segment-") as directory:
                source = Path(directory) / "recording.webm"
                segment = Path(directory) / "segment.webm"
                with source.open("wb") as merged:
                    for sequence, (key, _, _) in enumerate(chunks):
                        downloaded = Path(directory) / f"chunk-{sequence}.media"
                        self.storage.download_to(key, downloaded)
                        with downloaded.open("rb") as piece:
                            shutil.copyfileobj(piece, merged)
                self.processor.extract_audio_segment(source, segment, start_offset_ms, end_offset_ms)
                transcript = self.processor.transcribe(segment)
            status, text = TranscriptionStatus.COMPLETED, transcript
        except Exception:
            status, text = TranscriptionStatus.FAILED, None
        with self.sessions() as db:
            response = db.get(CandidateResponse, response_id)
            if response:
                response.transcription_status, response.transcript_text = status, text
                db.commit()
