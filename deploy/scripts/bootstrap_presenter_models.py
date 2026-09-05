"""Download the private MuseTalk runtime weights into an existing checkout."""

from __future__ import annotations

import argparse
import urllib.request
from pathlib import Path

import gdown
from huggingface_hub import snapshot_download


def download_models(root: Path) -> None:
    """Populate ``root/models`` with the weights required by MuseTalk 1.5."""
    models = root / "models"
    snapshot_download(
        "TMElyralab/MuseTalk",
        local_dir=models,
        allow_patterns=["musetalkV15/*"],
    )
    snapshot_download(
        "stabilityai/sd-vae-ft-mse",
        local_dir=models / "sd-vae",
        allow_patterns=["config.json", "diffusion_pytorch_model.bin"],
    )
    snapshot_download(
        "openai/whisper-tiny",
        local_dir=models / "whisper",
        allow_patterns=["config.json", "pytorch_model.bin", "preprocessor_config.json"],
    )
    snapshot_download(
        "yzd-v/DWPose",
        local_dir=models / "dwpose",
        allow_patterns=["dw-ll_ucoco_384.pth"],
    )

    face_models = models / "face-parse-bisent"
    face_models.mkdir(parents=True, exist_ok=True)
    parser = face_models / "79999_iter.pth"
    if not parser.is_file() or parser.stat().st_size == 0:
        downloaded = gdown.download(
            id="154JgKpzCPW82qINcVieuPH3fZ2e0P812",
            output=str(parser),
            quiet=False,
        )
        if not downloaded:
            raise RuntimeError("face parser model download failed")
    resnet = face_models / "resnet18-5c106cde.pth"
    if not resnet.is_file() or resnet.stat().st_size == 0:
        urllib.request.urlretrieve(
            "https://download.pytorch.org/models/resnet18-5c106cde.pth",
            resnet,
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("musetalk_root", type=Path)
    args = parser.parse_args()
    if not (args.musetalk_root / "scripts" / "inference.py").is_file():
        raise SystemExit("MuseTalk checkout is missing scripts/inference.py")
    download_models(args.musetalk_root)


if __name__ == "__main__":
    main()
