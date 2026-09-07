"""Rebuild one playable recording from its durable browser chunks."""

import sys
import tempfile
from pathlib import Path

import boto3
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.interview import InterviewRecording, InterviewRecordingChunk
from app.services.audio_processing import normalize_media_stream


session_id = sys.argv[1]
engine = create_engine(settings.database_url)
client = boto3.client(
    "s3",
    endpoint_url=settings.s3_endpoint_url,
    aws_access_key_id=settings.s3_access_key,
    aws_secret_access_key=settings.s3_secret_key,
)

with Session(engine) as db:
    recording = db.scalar(
        select(InterviewRecording).where(InterviewRecording.session_id == session_id)
    )
    if recording is None:
        raise SystemExit("recording not found")
    chunks = list(
        db.scalars(
            select(InterviewRecordingChunk)
            .where(
                InterviewRecordingChunk.recording_id == recording.id,
                InterviewRecordingChunk.uploaded_at.is_not(None),
            )
            .order_by(InterviewRecordingChunk.sequence)
        )
    )

extension = "mp4" if recording.content_type == "video/mp4" else "webm"
with tempfile.TemporaryDirectory(prefix="ai-interviewer-recompose-") as directory:
    root = Path(directory)
    raw = root / f"raw.{extension}"
    normalized = root / f"full.{extension}"
    with raw.open("wb") as merged:
        for sequence, chunk in enumerate(chunks):
            piece = root / f"chunk-{sequence}.{extension}"
            client.download_file(settings.s3_bucket, chunk.storage_key, str(piece))
            with piece.open("rb") as source:
                merged.write(source.read())
    normalize_media_stream(raw, normalized, settings.ffmpeg_binary)
    client.upload_file(
        str(normalized),
        settings.s3_bucket,
        f"{recording.storage_key}/full.{extension}",
        ExtraArgs={"ContentType": recording.content_type},
    )
    print(f"recomposed {normalized.stat().st_size} bytes")
