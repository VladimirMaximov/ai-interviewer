"""Client for a private, localhost-only persistent XTTS worker."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen


class XttsHttpProvider:
    def __init__(self, endpoint: str, voice: str = "Claribel Dervla") -> None:
        self._endpoint = endpoint.rstrip("/") + "/synthesize"
        self._voice = voice

    def synthesize(self, text: str, *, output_path: Path) -> Path:
        if not text.strip():
            raise ValueError("question text is required")
        request = Request(
            self._endpoint,
            data=json.dumps({"text": text, "speaker": self._voice}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=45) as response:
                audio = response.read()
        except URLError as error:
            raise RuntimeError("Local XTTS worker is unavailable") from error
        if not audio:
            raise RuntimeError("XTTS worker returned no audio")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(audio)
        return output_path
