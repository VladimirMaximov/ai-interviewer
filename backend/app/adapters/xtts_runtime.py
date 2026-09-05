"""Persistent XTTS v2 adapter for the isolated GPU presenter worker."""

from __future__ import annotations

import importlib
import wave
from pathlib import Path
from typing import Callable


class XttsRuntime:
    def __init__(
        self,
        *,
        model_name: str = "tts_models/multilingual/multi-dataset/xtts_v2",
        device: str = "cuda",
        engine_factory: Callable[[], object] | None = None,
    ) -> None:
        self.model_name = model_name
        self.device = device
        self._engine_factory = engine_factory
        self._engine: object | None = None

    def _load(self) -> object:
        if self._engine is None:
            if self._engine_factory:
                engine = self._engine_factory()
            else:
                try:
                    engine = importlib.import_module("TTS.api").TTS(self.model_name)
                except (ImportError, AttributeError) as error:
                    raise RuntimeError("XTTS runtime is not installed") from error
            self._engine = engine.to(self.device)
        return self._engine

    def synthesize(
        self, text: str, *, speaker: str, output_path: Path, language: str = "ru"
    ) -> Path:
        normalized = text.strip()
        if not normalized:
            raise ValueError("question text is required")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        self._load().tts_to_file(
            text=normalized,
            speaker=speaker,
            language=language,
            file_path=str(output_path),
        )
        if not output_path.is_file() or output_path.stat().st_size < 44:
            raise RuntimeError("XTTS produced no WAV audio")
        try:
            with wave.open(str(output_path), "rb") as audio:
                if audio.getnframes() < 1 or audio.getframerate() < 8_000:
                    raise RuntimeError("XTTS produced invalid WAV audio")
        except (wave.Error, EOFError) as error:
            raise RuntimeError("XTTS produced invalid WAV audio") from error
        return output_path
