"""Local Russian speech-to-text through the GigaAM v3 package."""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any


class GigaAm3Provider:
    """Transcribe locally without sending candidate audio to a third party.

    The heavyweight GigaAM dependency is imported and the model is loaded only on
    the first transcription request. This keeps API startup and unit tests light.
    """

    def __init__(self, model_name: str = "v3_e2e_rnnt") -> None:
        self._model_name = model_name
        self._model: Any | None = None

    def transcribe(self, audio_path: Path, *, language: str = "ru") -> str:
        """Return an E2E transcript for a local audio file.

        GigaAM v3 is trained for Russian. ``language`` is accepted to satisfy the
        provider contract but non-Russian recognition is deliberately rejected,
        rather than pretending that the configured model supports it.
        """
        if language != "ru":
            raise ValueError("GigaAM v3 provider supports only Russian audio")
        if not audio_path.is_file():
            raise FileNotFoundError(audio_path)

        if self._model is None:
            try:
                gigaam = importlib.import_module("gigaam")
            except ImportError as error:
                raise RuntimeError(
                    "Local GigaAM is not installed; install the GigaAM package and its torch extra"
                ) from error
            self._model = gigaam.load_model(self._model_name)

        result = self._model.transcribe(audio_path)
        transcript = getattr(result, "text", result)
        if not isinstance(transcript, str) or not transcript.strip():
            raise RuntimeError("GigaAM returned no transcription text")
        return transcript.strip()
