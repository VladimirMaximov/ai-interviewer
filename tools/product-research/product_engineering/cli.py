"""Command-line entrypoint."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from .api import OpenAIClient, OpenAIError
from .pipeline import PipelineConfig, ProductEngineeringPipeline
from .storage import slugify


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="product-engineering",
        description=(
            "Research commercial products and produce segments, ICPs, synthetic interviews, "
            "Pain Maps, JTBD, VPCs, ranked hypotheses, and Lean Canvases."
        ),
    )
    parser.add_argument("direction", nargs="?", help="Product or market direction to research")
    parser.add_argument("--model", help="OpenAI model ID (default: gpt-4.1)")
    parser.add_argument("--max-products", type=int, help="Maximum products (default: 3)")
    parser.add_argument("--max-segments", type=int, help="Segments per product (default: 5)")
    parser.add_argument("--page-timeout", type=float, help="Website timeout in seconds (default: 20)")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("runs"),
        help="Parent directory for a new run (default: ./runs)",
    )
    parser.add_argument("--resume", type=Path, help="Resume an existing run directory")
    parser.add_argument(
        "--api-key-env",
        default="OPENAI_API_KEY",
        help="Environment variable containing the API key",
    )
    parser.add_argument(
        "--base-url",
        default=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        help="Responses API base URL",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate options and print the expected work without API calls",
    )
    return parser


def _load_resume_config(path: Path) -> dict[str, Any]:
    manifest = path / "manifest.json"
    if not manifest.exists():
        raise ValueError(f"Resume directory has no manifest.json: {path}")
    with manifest.open("r", encoding="utf-8") as stream:
        data = json.load(stream)
    config = data.get("config")
    if not isinstance(config, dict):
        raise ValueError(f"Invalid manifest config: {manifest}")
    return config


def _resolve_config(args: argparse.Namespace) -> tuple[PipelineConfig, Path]:
    previous: dict[str, Any] = _load_resume_config(args.resume) if args.resume else {}
    direction = args.direction or previous.get("direction")
    if not direction:
        raise ValueError("direction is required for a new run")
    config = PipelineConfig(
        direction=direction,
        model=args.model or previous.get("model", "gpt-4.1"),
        max_products=(
            args.max_products if args.max_products is not None else previous.get("max_products", 3)
        ),
        max_segments=(
            args.max_segments if args.max_segments is not None else previous.get("max_segments", 5)
        ),
        page_timeout=(
            args.page_timeout if args.page_timeout is not None else previous.get("page_timeout", 20.0)
        ),
    )
    config.validate()
    if args.resume:
        run_dir = args.resume
    else:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        run_dir = args.output_dir / f"{timestamp}-{slugify(direction)}"
    return config, run_dir


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        config, run_dir = _resolve_config(args)
        estimated_calls = 1 + config.max_products * (2 + 7 * config.max_segments)
        if args.dry_run:
            print(
                json.dumps(
                    {
                        "config": config.__dict__,
                        "run_dir": str(run_dir.resolve()),
                        "maximum_api_calls": estimated_calls,
                        "note": "Actual calls can be lower when resuming from checkpoints.",
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 0

        api_key = os.environ.get(args.api_key_env, "")
        if not api_key:
            raise ValueError(
                f"{args.api_key_env} is not set. Export it or run with --dry-run first."
            )
        client = OpenAIClient(
            api_key=api_key,
            model=config.model,
            base_url=args.base_url,
        )
        pipeline = ProductEngineeringPipeline(
            client=client,
            config=config,
            run_dir=run_dir,
            progress=lambda message: print(f"[product-engineering] {message}", file=sys.stderr),
        )
        pipeline.run()
        print(run_dir.resolve() / "result.json")
        return 0
    except (
        ValueError,
        RuntimeError,
        OpenAIError,
        OSError,
        json.JSONDecodeError,
        KeyError,
        TypeError,
    ) as exc:
        print(f"product-engineering: error: {exc}", file=sys.stderr)
        return 1
