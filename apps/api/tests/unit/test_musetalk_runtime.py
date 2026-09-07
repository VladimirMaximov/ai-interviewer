import subprocess
import tempfile
import unittest
from pathlib import Path

from app.adapters.musetalk_runtime import MuseTalkRuntime


class MuseTalkRuntimeTests(unittest.TestCase):
    def test_preprocesses_to_even_dimensions_and_copies_result(self) -> None:
        calls = []
        def runner(command, **kwargs):
            calls.append(command)
            if "scripts.inference" in command:
                result_dir = Path(command[command.index("--result_dir") + 1]) / "v15"
                result_dir.mkdir(parents=True); (result_dir / "result.mp4").write_bytes(b"mp4")
            elif command[0] == "ffmpeg":
                Path(command[-1]).write_bytes(b"jpg")
            return subprocess.CompletedProcess(command, 0, "", "")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); portrait = root / "source.jpg"; audio = root / "source.wav"
            portrait.write_bytes(b"jpg"); audio.write_bytes(b"wav")
            output = MuseTalkRuntime(root, runner=runner).render(portrait, audio, output_path=root / "out.mp4", workspace=root / "work")
            self.assertTrue(output.is_file())
            self.assertIn("scale=trunc(iw/2)*2:trunc(ih/2)*2", calls[0])

    def test_hides_subprocess_output_on_failure(self) -> None:
        def runner(command, **kwargs): return subprocess.CompletedProcess(command, 1, "", "secret details")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); portrait = root / "p.jpg"; audio = root / "a.wav"
            portrait.write_bytes(b"x"); audio.write_bytes(b"x")
            with self.assertRaisesRegex(RuntimeError, "portrait_preprocessing_failed"):
                MuseTalkRuntime(root, runner=runner).render(portrait, audio, output_path=root / "o.mp4", workspace=root / "w")


if __name__ == "__main__": unittest.main()
