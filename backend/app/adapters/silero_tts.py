"""Local Russian question-speech generation through a configured Silero helper."""

import subprocess
from pathlib import Path


class SileroTtsProvider:
    def __init__(self, helper: Path, voice: str = "kseniya") -> None:
        self._helper = helper
        self._voice = voice

    def synthesize(self, text: str, *, output_path: Path) -> Path:
        if not text.strip():
            raise ValueError("question text is required")
        if not self._helper.is_file():
            raise RuntimeError("Local Silero TTS helper is not installed")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [str(self._helper), "--voice", self._voice, "--output", str(output_path), "--text", text],
            check=True, capture_output=True, text=True,
        )
        if not output_path.is_file():
            raise RuntimeError("Silero TTS did not produce an audio file")
        return output_path
