"""Human-readable summary rendering for pipeline results."""

from __future__ import annotations

from typing import Any


def render_markdown(result: dict[str, Any]) -> str:
    metadata = result["metadata"]
    lines = [
        "# Product Engineering Research",
        "",
        f"Direction: {metadata['direction']}",
        "",
        (
            "> Synthetic interviews and their quotes are ideation artifacts. "
            "They are not evidence of real customer demand."
        ),
        "",
    ]

    for product in result.get("products", []):
        candidate = product["candidate"]
        description = product["description"]
        lines.extend(
            [
                f"## {description.get('name') or candidate.get('name')}",
                "",
                f"Official URL: {candidate.get('url')}",
                "",
                description.get("summary", ""),
                "",
            ]
        )
        for analysis in product.get("segment_analyses", []):
            segment = analysis["segment"]
            best = analysis["best_hypothesis"]
            canvas = analysis["lean_canvas"]
            lines.extend(
                [
                    f"### {segment['name']}",
                    "",
                    segment["description"],
                    "",
                    f"Top hypothesis (RICE {best['rice_score']}): {best['description']}",
                    "",
                    f"Validation metric: {best['metric_to_validate']}",
                    "",
                    f"Value proposition: {canvas['unique_value_proposition']}",
                    "",
                ]
            )
    return "\n".join(lines).rstrip() + "\n"
