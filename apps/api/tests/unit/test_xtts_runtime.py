import tempfile
import unittest
import wave
from pathlib import Path

from app.adapters.xtts_runtime import XttsRuntime


class FakeEngine:
    def __init__(self) -> None:
        self.device = None
        self.calls = []

    def to(self, device):
        self.device = device
        return self

    def tts_to_file(self, **kwargs):
        self.calls.append(kwargs)
        with wave.open(kwargs["file_path"], "wb") as output:
            output.setnchannels(1); output.setsampwidth(2); output.setframerate(24_000)
            output.writeframes(b"\0\0" * 100)


class XttsRuntimeTests(unittest.TestCase):
    def test_reuses_gpu_model_and_preserves_mixed_language_text(self) -> None:
        engine = FakeEngine(); loads = 0
        def factory():
            nonlocal loads; loads += 1; return engine
        runtime = XttsRuntime(engine_factory=factory)
        with tempfile.TemporaryDirectory() as directory:
            for name in ("one.wav", "two.wav"):
                runtime.synthesize("Как работает PostgreSQL?", speaker="demo", output_path=Path(directory) / name)
        self.assertEqual(loads, 1)
        self.assertEqual(engine.device, "cuda")
        self.assertEqual(engine.calls[0]["text"], "Как работает PostgreSQL?")

    def test_rejects_empty_text_before_model_load(self) -> None:
        with self.assertRaises(ValueError):
            XttsRuntime(engine_factory=lambda: FakeEngine()).synthesize(" ", speaker="demo", output_path=Path("unused.wav"))


if __name__ == "__main__": unittest.main()
