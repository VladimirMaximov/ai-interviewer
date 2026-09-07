"""RouterAI-compatible remote transcription; disabled until a key is configured."""

import base64
import json
import urllib.error
import urllib.request
from pathlib import Path


class RouterAiTranscriptionProvider:
    def __init__(self, api_key: str | None, base_url: str) -> None:
        self._api_key = api_key
        self._url = f"{base_url.rstrip('/')}/audio/transcriptions"

    def transcribe(self, audio_path: Path, *, language: str = "ru") -> str:
        if not self._api_key:
            raise RuntimeError("RouterAI API key is not configured")
        if not audio_path.is_file():
            raise FileNotFoundError(audio_path)
        body = json.dumps({
            "model": "openai/gpt-4o-mini-transcribe",
            "input_audio": {
                "data": base64.b64encode(audio_path.read_bytes()).decode("ascii"),
                "format": audio_path.suffix.removeprefix(".") or "webm",
            },
            "language": language,
        }).encode("utf-8")
        request = urllib.request.Request(
            self._url,
            data=body,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                payload = json.loads(response.read())
        except urllib.error.URLError as error:
            raise RuntimeError("RouterAI transcription request failed") from error
        text = payload.get("text")
        if not isinstance(text, str):
            raise RuntimeError("RouterAI returned no transcription text")
        return text
