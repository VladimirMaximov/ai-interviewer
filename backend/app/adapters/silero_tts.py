"""Local Russian question-speech generation through a configured Silero helper."""

import subprocess
import sys
from pathlib import Path


class SileroTtsProvider:
    def __init__(
        self, helper: Path, voice: str = "aidar", python_binary: str | None = None
    ) -> None:
        self._helper = helper
        self._voice = voice
        self._python_binary = python_binary

    def synthesize(self, text: str, *, output_path: Path) -> Path:
        if not text.strip():
            raise ValueError("question text is required")
        if not self._helper.is_file():
            raise RuntimeError("Local Silero TTS helper is not installed")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        command = [str(self._helper)]
        if self._helper.suffix == ".py":
            command = [self._python_binary or sys.executable, str(self._helper)]
        subprocess.run(
            [*command, "--voice", self._voice, "--output", str(output_path), "--text", text],
            check=True, capture_output=True, text=True,
        )
        if not output_path.is_file():
            raise RuntimeError("Silero TTS did not produce an audio file")
        return output_path
