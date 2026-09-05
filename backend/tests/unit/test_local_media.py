import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app.adapters.gigaam3 import GigaAm3Provider
from app.adapters.silero_tts import SileroTtsProvider
from app.adapters.whisper_cpp import WhisperCppProvider
from app.adapters.routerai_transcription import RouterAiTranscriptionProvider


class LocalMediaTests(unittest.TestCase):
    def test_gigaam_requires_local_package(self) -> None:
        provider = GigaAm3Provider()
        with tempfile.NamedTemporaryFile(suffix=".wav") as audio:
            with patch("app.adapters.gigaam3.importlib.import_module", side_effect=ImportError):
                with self.assertRaisesRegex(RuntimeError, "not installed"):
                    provider.transcribe(Path(audio.name))

    def test_gigaam_rejects_non_russian_audio(self) -> None:
        provider = GigaAm3Provider()
        with self.assertRaisesRegex(ValueError, "only Russian"):
            provider.transcribe(Path("response.wav"), language="en")

    def test_gigaam_accepts_silence_as_completed_empty_transcript(self) -> None:
        provider = GigaAm3Provider()
        model = SimpleNamespace(transcribe=lambda _: "   ")
        with tempfile.NamedTemporaryFile(suffix=".wav") as audio:
            with patch("app.adapters.gigaam3.importlib.import_module", return_value=SimpleNamespace(load_model=lambda _: model)):
                self.assertEqual(provider.transcribe(Path(audio.name)), "")

    def test_whisper_requires_installed_binary_and_model(self) -> None:
        provider = WhisperCppProvider(Path("/missing/whisper-cli"), Path("/missing/small.bin"))
        with self.assertRaisesRegex(RuntimeError, "not installed"):
            provider.transcribe(Path("response.wav"))

    def test_silero_rejects_empty_question_without_launching_process(self) -> None:
        provider = SileroTtsProvider(Path("/missing/silero-tts"))
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                provider.synthesize("  ", output_path=Path(directory) / "question.wav")

    def test_routerai_requires_explicit_key(self) -> None:
        provider = RouterAiTranscriptionProvider(None, "https://routerai.ru/api/v1")
        with self.assertRaisesRegex(RuntimeError, "not configured"):
            provider.transcribe(Path("response.webm"))
