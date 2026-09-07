import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.api.health import stt_readiness


class HealthTests(unittest.TestCase):
    def test_gigaam_readiness_requires_installed_package(self) -> None:
        with (
            patch("app.api.health.settings.transcription_provider", "gigaam3"),
            patch("app.api.health.find_spec", return_value=None),
        ):
            self.assertEqual(stt_readiness(), "unavailable")
        with (
            patch("app.api.health.settings.transcription_provider", "gigaam3"),
            patch("app.api.health.find_spec", return_value=object()),
        ):
            self.assertEqual(stt_readiness(), "ok")

    def test_whisper_readiness_requires_binary_and_model(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            model = Path(directory) / "model.bin"
            model.write_bytes(b"model")
            with (
                patch("app.api.health.settings.transcription_provider", "whisper_cpp"),
                patch("app.api.health.settings.whisper_cpp_binary", "whisper-cli"),
                patch("app.api.health.settings.whisper_cpp_model", str(model)),
                patch("app.api.health.shutil.which", return_value=None),
            ):
                self.assertEqual(stt_readiness(), "unavailable")
            with (
                patch("app.api.health.settings.transcription_provider", "whisper_cpp"),
                patch("app.api.health.settings.whisper_cpp_binary", "whisper-cli"),
                patch("app.api.health.settings.whisper_cpp_model", str(model)),
                patch("app.api.health.shutil.which", return_value="/usr/bin/whisper-cli"),
            ):
                self.assertEqual(stt_readiness(), "ok")


if __name__ == "__main__":
    unittest.main()
