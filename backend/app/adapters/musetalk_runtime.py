"""Validated subprocess boundary for MuseTalk 1.5 lip synchronization."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Callable


Runner = Callable[..., subprocess.CompletedProcess[str]]


class MuseTalkRuntime:
    def __init__(
        self,
        root: Path,
        *,
        python_binary: str = "python",
        ffmpeg_binary: str = "ffmpeg",
        timeout_seconds: int = 120,
        runner: Runner = subprocess.run,
    ) -> None:
        self.root = root
        self.python_binary = python_binary
        self.ffmpeg_binary = ffmpeg_binary
        self.timeout_seconds = timeout_seconds
        self.runner = runner

    def render(
        self, portrait: Path, audio: Path, *, output_path: Path, workspace: Path
    ) -> Path:
        if not portrait.is_file() or not audio.is_file():
            raise ValueError("portrait and audio files are required")
        workspace.mkdir(parents=True, exist_ok=True)
        even_portrait = workspace / "portrait.jpg"
        self._run([
            self.ffmpeg_binary, "-y", "-v", "error", "-i", str(portrait),
            "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2", str(even_portrait),
        ], "portrait_preprocessing_failed")
        local_audio = workspace / "question.wav"
        shutil.copyfile(audio, local_audio)
        config = workspace / "inference.yaml"
        config.write_text(
            "task_0:\n"
            f"  video_path: {even_portrait.as_posix()}\n"
            f"  audio_path: {local_audio.as_posix()}\n",
            encoding="utf-8",
        )
        result_dir = workspace / "results"
        self._run([
            self.python_binary, "-m", "scripts.inference",
            "--inference_config", str(config), "--result_dir", str(result_dir),
            "--unet_model_path", "models/musetalkV15/unet.pth",
            "--unet_config", "models/musetalkV15/musetalk.json",
            "--version", "v15", "--use_float16", "--batch_size", "4",
            "--fps", "25",
        ], "avatar_render_failed", cwd=self.root)
        candidates = sorted(result_dir.rglob("*.mp4"))
        if not candidates or candidates[-1].stat().st_size == 0:
            raise RuntimeError("avatar_render_missing_output")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(candidates[-1], output_path)
        self._run([
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(output_path),
        ], "avatar_output_invalid")
        return output_path

    def _run(self, command: list[str], error_code: str, **kwargs: object) -> None:
        try:
            result = self.runner(
                command, capture_output=True, text=True, check=False,
                timeout=self.timeout_seconds, **kwargs,
            )
        except subprocess.TimeoutExpired as error:
            raise RuntimeError(f"{error_code}:timeout") from error
        if result.returncode != 0:
            raise RuntimeError(error_code)
