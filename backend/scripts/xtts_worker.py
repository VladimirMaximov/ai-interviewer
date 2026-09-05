"""Private persistent localhost worker for multilingual XTTS v2 synthesis."""

from __future__ import annotations

import json
import tempfile
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from TTS.api import TTS


class XttsWorker:
    def __init__(self) -> None:
        self.tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to("cpu")
        self.cache: dict[tuple[str, str], bytes] = {}
        self.lock = threading.Lock()

    def synthesize(self, text: str, speaker: str) -> bytes:
        key = (text, speaker)
        with self.lock:
            if key not in self.cache:
                with tempfile.TemporaryDirectory(prefix="ai-interviewer-xtts-") as directory:
                    destination = Path(directory) / "speech.wav"
                    self.tts.tts_to_file(
                        text=text, speaker=speaker, language="ru", file_path=str(destination)
                    )
                    self.cache[key] = destination.read_bytes()
        return self.cache[key]


class Handler(BaseHTTPRequestHandler):
    worker: XttsWorker

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/synthesize":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        try:
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            text = body["text"].strip()
            if not text:
                raise ValueError("text is required")
            audio = self.worker.synthesize(text, body.get("speaker", "Claribel Dervla"))
        except Exception:
            self.send_error(HTTPStatus.SERVICE_UNAVAILABLE)
            return
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "audio/wav")
        self.send_header("Content-Length", str(len(audio)))
        self.end_headers()
        self.wfile.write(audio)

    def log_message(self, format: str, *args: object) -> None:
        return


def main() -> None:
    Handler.worker = XttsWorker()
    ThreadingHTTPServer(("127.0.0.1", 8001), Handler).serve_forever()


if __name__ == "__main__":
    main()
