"""End-to-end, resumable Product Engineering research pipeline."""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from . import prompts
from .api import OpenAIClient
from .report import render_markdown
from .schemas import (
    HYPOTHESES_SCHEMA,
    ICP_SCHEMA,
    INTERVIEW_SCHEMA,
    JTBD_SCHEMA,
    LEAN_CANVAS_SCHEMA,
    PAIN_MAP_SCHEMA,
    PRODUCT_DESCRIPTION_SCHEMA,
    PRODUCT_RESEARCH_SCHEMA,
    SEGMENTS_SCHEMA,
    VPC_SCHEMA,
    limited_schema,
)
from .scraper import fetch_page
from .storage import StageStore, slugify


Progress = Callable[[str], None]
Fetcher = Callable[..., dict[str, Any]]


@dataclass(frozen=True)
class PipelineConfig:
    direction: str
    model: str = "gpt-4.1"
    max_products: int = 3
    max_segments: int = 5
    page_timeout: float = 20.0

    def validate(self) -> None:
        if not self.direction.strip():
            raise ValueError("direction must not be empty")
        if not 1 <= self.max_products <= 20:
            raise ValueError("max_products must be between 1 and 20")
        if not 1 <= self.max_segments <= 10:
            raise ValueError("max_segments must be between 1 and 10")
        if self.page_timeout <= 0:
            raise ValueError("page_timeout must be positive")


def normalize_url(url: str) -> str:
    parsed = urlsplit(url.strip())
    path = parsed.path.rstrip("/") or "/"
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), path, parsed.query, ""))


def deduplicate_products(products: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    output: list[dict[str, Any]] = []
    for product in products:
        url = product.get("url")
        if not isinstance(url, str):
            continue
        key = normalize_url(url)
        if key in seen:
            continue
        seen.add(key)
        clean = dict(product)
        clean["url"] = key
        output.append(clean)
    return output


def pain_priority_score(pain: dict[str, Any]) -> int:
    weighted = (
        float(pain["severity"]) * 0.4
        + float(pain["frequency"]) * 0.3
        + float(pain["reach"]) * 0.2
        + float(pain["confidence"]) * 0.1
    ) * 10
    return int(math.floor(weighted + 0.5))


def normalize_pain_map(data: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(data)
    normalized["pains"] = []
    for pain in data.get("pains", []):
        item = dict(pain)
        item["priority_score"] = pain_priority_score(item)
        normalized["pains"].append(item)
    normalized["pains"].sort(key=lambda pain: pain["priority_score"], reverse=True)
    return normalized


def normalize_and_rank_hypotheses(data: dict[str, Any]) -> list[dict[str, Any]]:
    ranked: list[dict[str, Any]] = []
    for raw in data.get("hypotheses", []):
        item = dict(raw)
        reach = max(1, int(item["reach"]))
        impact = float(item["impact"])
        confidence = min(0.7, max(0.0, float(item["confidence"])))
        effort = max(0.5, math.floor(float(item["effort"]) * 2 + 0.5) / 2)
        item.update(
            {
                "reach": reach,
                "impact": impact,
                "confidence": confidence,
                "effort": effort,
                "rice_score": round((reach * impact * confidence) / effort, 1),
            }
        )
        ranked.append(item)
    ranked.sort(
        key=lambda hypothesis: (
            hypothesis["rice_score"],
            hypothesis["impact"],
            hypothesis["reach"],
            -hypothesis["effort"],
        ),
        reverse=True,
    )
    return ranked


class ProductEngineeringPipeline:
    def __init__(
        self,
        *,
        client: OpenAIClient,
        config: PipelineConfig,
        run_dir: Path,
        fetcher: Fetcher = fetch_page,
        progress: Progress | None = None,
    ) -> None:
        config.validate()
        self.client = client
        self.config = config
        self.store = StageStore(run_dir)
        self.fetcher = fetcher
        self.progress = progress or (lambda _: None)

    def _generate(
        self,
        *,
        stage: str,
        prompt: str,
        schema: dict[str, Any],
        use_web_search: bool = False,
        max_output_tokens: int = 12_000,
    ) -> dict[str, Any]:
        self.progress(f"Generating {stage}")
        return self.client.create_json(
            prompt=prompt,
            schema=schema,
            schema_name=stage,
            instructions=prompts.INSTRUCTIONS,
            use_web_search=use_web_search,
            max_output_tokens=max_output_tokens,
        )

    def _manifest(self) -> dict[str, Any]:
        manifest_path = self.store.path("manifest.json")
        if manifest_path.exists():
            manifest = self.store.load("manifest.json")
            existing = manifest["config"]
            current = asdict(self.config)
            if existing != current:
                raise ValueError(
                    "Resume configuration differs from manifest. Use the original direction, "
                    "model, limits, and timeout, or start a new run directory."
                )
            return manifest
        manifest = {
            "pipeline_version": 1,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "config": asdict(self.config),
        }
        self.store.save("manifest.json", manifest)
        return manifest

    def _fetch(self, candidate: dict[str, Any]) -> dict[str, Any]:
        try:
            return self.fetcher(candidate["url"], timeout=self.config.page_timeout)
        except Exception as exc:  # continue with search evidence when a site blocks automation
            return {
                "url": candidate["url"],
                "requested_url": candidate["url"],
                "fetch_error": f"{type(exc).__name__}: {exc}",
                "title": None,
                "description": None,
                "lang": None,
                "h1": [],
                "h2": [],
                "h3": [],
                "h4": [],
            }

    def run(self) -> dict[str, Any]:
        manifest = self._manifest()
        research_schema = limited_schema(
            PRODUCT_RESEARCH_SCHEMA, ("products",), self.config.max_products
        )
        research = self.store.cached(
            "research.json",
            lambda: self._generate(
                stage="product_research",
                prompt=prompts.product_research(
                    self.config.direction, self.config.max_products
                ),
                schema=research_schema,
                use_web_search=True,
            ),
        )
        products = deduplicate_products(research.get("products", []))[
            : self.config.max_products
        ]
        if not products:
            raise RuntimeError("Product research returned no usable official URLs")

        product_results: list[dict[str, Any]] = []
        for product_index, candidate in enumerate(products, start=1):
            product_slug = f"{product_index:02d}-{slugify(candidate.get('name', 'product'))}"
            base = Path("products") / product_slug
            self.progress(f"Processing product {product_index}/{len(products)}: {candidate['name']}")

            page = self.store.cached(base / "page.json", lambda c=candidate: self._fetch(c))
            description = self.store.cached(
                base / "description.json",
                lambda c=candidate, p=page: self._generate(
                    stage="product_description",
                    prompt=prompts.product_description(c, p),
                    schema=PRODUCT_DESCRIPTION_SCHEMA,
                    max_output_tokens=6_000,
                ),
            )
            product_context = {
                "official_url": candidate["url"],
                "discovery_evidence": candidate,
                "page": page,
                "description": description,
            }
            segments_schema = limited_schema(
                SEGMENTS_SCHEMA, ("segments",), self.config.max_segments
            )
            segment_data = self.store.cached(
                base / "segments.json",
                lambda pc=product_context: self._generate(
                    stage="customer_segments",
                    prompt=prompts.segments(pc, self.config.max_segments),
                    schema=segments_schema,
                    max_output_tokens=6_000,
                ),
            )
            segment_results: list[dict[str, Any]] = []
            for segment_index, segment in enumerate(
                segment_data.get("segments", [])[: self.config.max_segments], start=1
            ):
                segment_slug = f"{segment_index:02d}-{slugify(segment.get('name', 'segment'))}"
                segment_base = base / "segments" / segment_slug
                self.progress(
                    f"Processing segment {segment_index}/{len(segment_data['segments'])}: "
                    f"{segment['name']}"
                )

                icp_data = self.store.cached(
                    segment_base / "icp.json",
                    lambda pc=product_context, s=segment: self._generate(
                        stage="ideal_customer_profile",
                        prompt=prompts.icp(pc, s),
                        schema=ICP_SCHEMA,
                    ),
                )
                interview_data = self.store.cached(
                    segment_base / "synthetic_interview.json",
                    lambda pc=product_context, s=segment, i=icp_data: self._generate(
                        stage="synthetic_interview",
                        prompt=prompts.interview(pc, s, i),
                        schema=INTERVIEW_SCHEMA,
                    ),
                )
                pain_data = self.store.cached(
                    segment_base / "pain_map.json",
                    lambda s=segment, i=interview_data: self._generate(
                        stage="pain_map",
                        prompt=prompts.pain_map(s, i),
                        schema=PAIN_MAP_SCHEMA,
                    ),
                )
                pain_data = normalize_pain_map(pain_data)
                self.store.save(segment_base / "pain_map.json", pain_data)

                jtbd_data = self.store.cached(
                    segment_base / "jtbd.json",
                    lambda s=segment, i=interview_data, p=pain_data: self._generate(
                        stage="jobs_to_be_done",
                        prompt=prompts.jtbd(s, i, p),
                        schema=JTBD_SCHEMA,
                    ),
                )
                vpc_data = self.store.cached(
                    segment_base / "value_proposition_canvas.json",
                    lambda pc=product_context, s=segment, p=pain_data, j=jtbd_data: self._generate(
                        stage="value_proposition_canvas",
                        prompt=prompts.vpc(pc, s, p, j),
                        schema=VPC_SCHEMA,
                    ),
                )
                hypothesis_context = {
                    "product": product_context,
                    "segment": segment,
                    "icp": icp_data,
                    "interview": interview_data,
                    "pain_map": pain_data,
                    "jtbd": jtbd_data,
                    "value_proposition_canvas": vpc_data,
                }
                hypothesis_data = self.store.cached(
                    segment_base / "hypotheses_raw.json",
                    lambda hc=hypothesis_context: self._generate(
                        stage="product_hypotheses",
                        prompt=prompts.hypotheses(hc),
                        schema=HYPOTHESES_SCHEMA,
                    ),
                )
                ranked_hypotheses = normalize_and_rank_hypotheses(hypothesis_data)
                if not ranked_hypotheses:
                    raise RuntimeError(f"No hypotheses generated for {segment['name']}")
                self.store.save(segment_base / "hypotheses_ranked.json", ranked_hypotheses)
                best = ranked_hypotheses[0]

                lean_data = self.store.cached(
                    segment_base / "lean_canvas.json",
                    lambda hc=hypothesis_context, b=best: self._generate(
                        stage="lean_canvas",
                        prompt=prompts.lean_canvas(hc, b),
                        schema=LEAN_CANVAS_SCHEMA,
                    ),
                )
                segment_results.append(
                    {
                        "segment": segment,
                        "icp": icp_data,
                        "interview": interview_data,
                        "pain_map": pain_data,
                        "jtbd": jtbd_data,
                        "value_proposition_canvas": vpc_data,
                        "hypotheses": ranked_hypotheses,
                        "best_hypothesis": best,
                        "lean_canvas": lean_data,
                    }
                )

            product_results.append(
                {
                    "candidate": candidate,
                    "page": page,
                    "description": description,
                    "segments": segment_data["segments"],
                    "segment_analyses": segment_results,
                }
            )

        result = {
            "metadata": {
                "direction": self.config.direction,
                "model": self.config.model,
                "created_at": manifest["created_at"],
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "evidence_notice": (
                    "Web and official-page facts are research evidence. Interviews and their "
                    "quotes are synthetic ideation artifacts and require real-customer validation."
                ),
            },
            "research": research,
            "products": product_results,
        }
        self.store.save("result.json", result)
        self.store.save_text("report.md", render_markdown(result))
        self.progress("Pipeline complete")
        return result
