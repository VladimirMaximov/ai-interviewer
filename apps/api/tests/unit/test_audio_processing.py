import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.services.audio_processing import AudioProcessingError, WhisperAudioProcessor


class RecordingProvider:
    def __init__(self) -> None:
        self.path: Path | None = None
        self.language: str | None = None

    def transcribe(self, audio_path: Path, *, language: str) -> str:
        self.path = audio_path
        self.language = language
        return "Текст ответа"


class AudioProcessingTests(unittest.TestCase):
    def test_normalizes_browser_audio_before_transcription(self) -> None:
        provider = RecordingProvider()
        processor = WhisperAudioProcessor(provider, ffmpeg_binary="ffmpeg-test")

        def fake_run(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
            output = Path(command[-1])
            output.write_bytes(b"wav")
            self.assertEqual(command[:2], ["ffmpeg-test", "-nostdin"])
            self.assertIn("-ar", command)
            self.assertIn("16000", command)
            self.assertIn("pcm_s16le", command)
            return subprocess.CompletedProcess(command, 0)

        with tempfile.NamedTemporaryFile(suffix=".webm") as source:
            source.write(b"webm")
            source.flush()
            with patch("app.services.audio_processing.subprocess.run", side_effect=fake_run):
                transcript = processor.transcribe(Path(source.name))

        self.assertEqual(transcript, "Текст ответа")
        self.assertEqual(provider.language, "ru")
        self.assertIsNotNone(provider.path)
        self.assertEqual(provider.path.name, "response.wav")
        self.assertFalse(provider.path.exists())

    def test_conversion_failure_hides_command_details(self) -> None:
        processor = WhisperAudioProcessor(RecordingProvider())
        with tempfile.NamedTemporaryFile(suffix=".webm") as source:
            with patch(
                "app.services.audio_processing.subprocess.run",
                side_effect=subprocess.CalledProcessError(1, ["ffmpeg", "secret-file"]),
            ):
                with self.assertRaisesRegex(AudioProcessingError, "could not be prepared"):
                    processor.transcribe(Path(source.name))
