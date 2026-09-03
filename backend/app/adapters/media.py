"""Provider interfaces; concrete calls are never made by API routes directly."""

from pathlib import Path
from typing import Protocol


class TranscriptionProvider(Protocol):
    def transcribe(self, audio_path: Path, *, language: str) -> str: ...


class QuestionSpeechProvider(Protocol):
    def synthesize(self, text: str, *, output_path: Path) -> Path: ...
