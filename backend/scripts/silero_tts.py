"""Generate one Russian question WAV using a locally cached Silero model."""

from __future__ import annotations

import argparse
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--text", required=True)
    parser.add_argument("--voice", default="kseniya")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    if not args.text.strip():
        raise ValueError("text must not be empty")

    import torch

    model, _ = torch.hub.load(
        "snakers4/silero-models",
        "silero_tts",
        language="ru",
        speaker="v4_ru",
        trust_repo=True,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    model.save_wav(
        text=args.text,
        speaker=args.voice,
        sample_rate=48_000,
        audio_path=str(output),
    )


if __name__ == "__main__":
    main()
