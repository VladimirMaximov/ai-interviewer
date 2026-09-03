"""Local multilingual speech-to-text using a preinstalled whisper.cpp binary."""

import subprocess
from pathlib import Path


class WhisperCppProvider:
    def __init__(self, binary: Path, model: Path) -> None:
        self._binary = binary
        self._model = model

    def transcribe(self, audio_path: Path, *, language: str = "ru") -> str:
        if not self._binary.is_file() or not self._model.is_file():
            raise RuntimeError("Local transcription model is not installed")
        result = subprocess.run(
            [str(self._binary), "-m", str(self._model), "-f", str(audio_path), "-l", language, "-nt"],
            check=True, capture_output=True, text=True,
        )
        return result.stdout.strip()
