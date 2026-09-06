"""Local preparation of browser-recorded audio for transcription."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from app.adapters.media import TranscriptionProvider


class AudioProcessingError(RuntimeError):
    """Raised when an uploaded response cannot be safely prepared for ASR."""


def normalize_media_stream(
    source_path: Path,
    destination: Path,
    ffmpeg_binary: str = "ffmpeg",
) -> None:
    """Remux a concatenated browser recording into one playable media file."""
    if not source_path.is_file() or source_path.stat().st_size == 0:
        raise AudioProcessingError("Media source is empty")
    try:
        subprocess.run(
            [ffmpeg_binary, "-nostdin", "-y", "-i", str(source_path), "-map", "0", "-c", "copy", str(destination)],
            check=True, capture_output=True, text=True, timeout=180,
        )
    except (OSError, subprocess.SubprocessError):
        try:
            subprocess.run(
                [ffmpeg_binary, "-nostdin", "-y", "-i", str(source_path), "-map", "0", "-c:v", "libvpx-vp9", "-c:a", "libopus", str(destination)],
                check=True, capture_output=True, text=True, timeout=300,
            )
        except (OSError, subprocess.SubprocessError) as error:
            raise AudioProcessingError("Media could not be normalized") from error
    if not destination.is_file() or destination.stat().st_size == 0:
        raise AudioProcessingError("Media normalization produced no usable file")


class WhisperAudioProcessor:
    """Convert arbitrary browser media to Whisper-compatible audio then transcribe it.

    The normalized WAV exists only in a per-request temporary directory and is
    removed once the provider finishes. The original audio remains in private
    object storage; it is never persisted under the application source tree.
    """

    def __init__(self, provider: TranscriptionProvider, ffmpeg_binary: str = "ffmpeg") -> None:
        self._provider = provider
        self._ffmpeg_binary = ffmpeg_binary

    def transcribe(self, source_path: Path, *, language: str = "ru") -> str:
        """Normalize ``source_path`` to 16-kHz mono PCM WAV and transcribe it."""
        if not source_path.is_file():
            raise FileNotFoundError(source_path)

        with tempfile.TemporaryDirectory(prefix="ai-interviewer-asr-") as directory:
            normalized_path = Path(directory) / "response.wav"
            try:
                subprocess.run(
                    [
                        self._ffmpeg_binary,
                        "-nostdin",
                        "-y",
                        "-i",
                        str(source_path),
                        "-ar",
                        "16000",
                        "-ac",
                        "1",
                        "-c:a",
                        "pcm_s16le",
                        str(normalized_path),
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
            except (OSError, subprocess.SubprocessError) as error:
                raise AudioProcessingError("Audio could not be prepared for transcription") from error

            if not normalized_path.is_file() or normalized_path.stat().st_size == 0:
                raise AudioProcessingError("Audio conversion produced no usable file")
            return self._provider.transcribe(normalized_path, language=language)

    def extract_audio_segment(self, source_path: Path, destination: Path,
                              start_offset_ms: int, end_offset_ms: int) -> None:
        """Extract an answer interval without retaining a second copy of media."""
        if end_offset_ms <= start_offset_ms:
            raise AudioProcessingError("Segment bounds are invalid")
        try:
            subprocess.run(
                [
                    self._ffmpeg_binary, "-nostdin", "-y", "-ss", str(start_offset_ms / 1000),
                    "-i", str(source_path), "-t", str((end_offset_ms - start_offset_ms) / 1000),
                    "-vn", "-c:a", "libopus", str(destination),
                ],
                check=True, capture_output=True, text=True, timeout=120,
            )
        except (OSError, subprocess.SubprocessError) as error:
            raise AudioProcessingError("Answer segment could not be prepared") from error
        if not destination.is_file() or destination.stat().st_size == 0:
            raise AudioProcessingError("Answer segment has no usable audio")
