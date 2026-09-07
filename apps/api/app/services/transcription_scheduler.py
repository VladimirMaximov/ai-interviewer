"""Request-safe background transcription with a fresh database session per job."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import shutil
import logging
from sqlalchemy.orm import sessionmaker
from app.adapters.storage import PrivateObjectStorage
from app.models.interview import CandidateResponse, TranscriptionStatus
from app.services.audio_processing import normalize_media_stream

logger = logging.getLogger(__name__)


class CeleryTranscriptionDispatcher:
    """Submit durable ASR work without loading speech models in the API."""

    def __init__(self, celery_app, queue: str) -> None:
        self.celery_app, self.queue = celery_app, queue

    def _send(self, task: str, args: list) -> None:
        self.celery_app.send_task(task, args=args, queue=self.queue)

    def schedule(self, response_id, key: str) -> None:
        self._send("app.workers.transcription_tasks.transcribe_response", [str(response_id), key])

    def schedule_segment(self, response_id, key: str, start_offset_ms: int, end_offset_ms: int) -> None:
        self._send("app.workers.transcription_tasks.transcribe_segment", [str(response_id), key, start_offset_ms, end_offset_ms])

    def schedule_segment_chunks(self, response_id, chunks, start_offset_ms: int, end_offset_ms: int) -> None:
        self._send("app.workers.transcription_tasks.transcribe_chunk_segment", [str(response_id), chunks, start_offset_ms, end_offset_ms])

    def schedule_runtime_evaluation(self, response_id) -> None:
        self._send("app.workers.transcription_tasks.evaluate_response", [str(response_id)])

    def schedule_finalization(self, response_id) -> None:
        self._send("app.workers.transcription_tasks.finalize_interview", [str(response_id)])

class TranscriptionScheduler:
    def __init__(self, sessions: sessionmaker, storage: PrivateObjectStorage, processor, runtime_evaluation=None) -> None:
        self.sessions, self.storage, self.processor, self.runtime_evaluation = sessions, storage, processor, runtime_evaluation
        self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="asr")
    def schedule(self, response_id, key: str) -> None:
        self.executor.submit(self._run, response_id, key)
    def schedule_segment(self, response_id, key: str, start_offset_ms: int, end_offset_ms: int) -> None:
        self.executor.submit(self._run_segment, response_id, key, start_offset_ms, end_offset_ms)
    def schedule_segment_chunks(self, response_id, chunks, start_offset_ms: int, end_offset_ms: int) -> None:
        self.executor.submit(self._run_chunk_segment, response_id, chunks, start_offset_ms, end_offset_ms)
    def schedule_runtime_evaluation(self, response_id) -> None:
        """Evaluate non-ASR answers, such as a saved coding solution, off-request."""
        if self.runtime_evaluation:
            self.executor.submit(self.runtime_evaluation.evaluate_completed_response, response_id)
    def _run(self, response_id, key: str) -> None:
        import tempfile
        try:
            with tempfile.TemporaryDirectory(prefix="ai-interviewer-job-") as directory:
                source = Path(directory) / "response.webm"; self.storage.download_to(key, source)
                transcript = self.processor.transcribe(source)
            status, text = TranscriptionStatus.COMPLETED, transcript
        except Exception:
            logger.exception("Response transcription failed")
            status, text = TranscriptionStatus.FAILED, None
        with self.sessions() as db:
            response = db.get(CandidateResponse, response_id)
            if response: response.transcription_status, response.transcript_text = status, text; db.commit()
        if status is TranscriptionStatus.COMPLETED and self.runtime_evaluation:
            self.runtime_evaluation.evaluate_completed_response(response_id)

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
            logger.exception("Response segment transcription failed")
            status, text = TranscriptionStatus.FAILED, None
        with self.sessions() as db:
            response = db.get(CandidateResponse, response_id)
            if response:
                response.transcription_status, response.transcript_text = status, text
                db.commit()
        if status is TranscriptionStatus.COMPLETED and self.runtime_evaluation:
            self.runtime_evaluation.evaluate_completed_response(response_id)

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
                normalized = Path(directory) / "recording-normalized.webm"
                normalize_media_stream(source, normalized, self.processor._ffmpeg_binary)
                self.processor.extract_audio_segment(normalized, segment, start_offset_ms, end_offset_ms)
                transcript = self.processor.transcribe(segment)
            status, text = TranscriptionStatus.COMPLETED, transcript
        except Exception:
            logger.exception("Chunk segment transcription failed")
            status, text = TranscriptionStatus.FAILED, None
        with self.sessions() as db:
            response = db.get(CandidateResponse, response_id)
            if response:
                response.transcription_status, response.transcript_text = status, text
                db.commit()
        if status is TranscriptionStatus.COMPLETED and self.runtime_evaluation:
            self.runtime_evaluation.evaluate_completed_response(response_id)
