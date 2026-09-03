"""Strict JSON Schemas used by the Product Engineering pipeline."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


JSONSchema = dict[str, Any]


def obj(properties: dict[str, JSONSchema], *, required: list[str] | None = None) -> JSONSchema:
    return {
        "type": "object",
        "properties": properties,
        "required": required or list(properties),
        "additionalProperties": False,
    }


def arr(items: JSONSchema, *, minimum: int | None = None, maximum: int | None = None) -> JSONSchema:
    schema: JSONSchema = {"type": "array", "items": items}
    if minimum is not None:
        schema["minItems"] = minimum
    if maximum is not None:
        schema["maxItems"] = maximum
    return schema


TEXT: JSONSchema = {"type": "string"}
STRING_LIST: JSONSchema = arr(TEXT)
SCORE_1_5: JSONSchema = {"type": "integer", "minimum": 1, "maximum": 5}


PRODUCT_RESEARCH_SCHEMA = obj(
    {
        "direction": TEXT,
        "products": arr(
            obj(
                {
                    "name": TEXT,
                    "url": TEXT,
                    "what_it_sells": TEXT,
                    "commercial_evidence": TEXT,
                    "source_urls": arr(TEXT, minimum=1),
                }
            ),
            minimum=1,
        ),
    }
)


PRODUCT_DESCRIPTION_SCHEMA = obj(
    {
        "name": TEXT,
        "summary": TEXT,
        "category": TEXT,
        "audience_clues": STRING_LIST,
        "key_features": STRING_LIST,
        "value_proposition": TEXT,
        "pricing_signals": STRING_LIST,
        "evidence_gaps": STRING_LIST,
    }
)


SEGMENTS_SCHEMA = obj(
    {
        "segments": arr(
            obj({"name": TEXT, "description": TEXT}),
            minimum=1,
        )
    }
)


ICP_SCHEMA = obj(
    {
        "customer_type": {"type": "string", "enum": ["B2B", "B2C", "B2G", "mixed"]},
        "industry_or_market_category": TEXT,
        "demographics": STRING_LIST,
        "firmographics": STRING_LIST,
        "geography": STRING_LIST,
        "psychographics": STRING_LIST,
        "behavioral_traits": STRING_LIST,
        "needs_and_goals": STRING_LIST,
        "purchase_triggers": STRING_LIST,
        "decision_making_process": STRING_LIST,
        "budget_or_spending_capacity": TEXT,
        "preferred_channels_and_touchpoints": STRING_LIST,
        "objections_and_responses": arr(
            obj({"objection": TEXT, "response": TEXT})
        ),
        "assumptions": STRING_LIST,
    }
)


INTERVIEW_SCHEMA = obj(
    {
        "evidence_type": {"type": "string", "enum": ["synthetic"]},
        "interviewee_profile": TEXT,
        "questions": arr(
            obj(
                {
                    "id": {"type": "integer", "minimum": 1},
                    "question": TEXT,
                    "answer": TEXT,
                }
            ),
            minimum=8,
            maximum=10,
        ),
        "validation_warning": TEXT,
    }
)


PAIN_MAP_SCHEMA = obj(
    {
        "segment": TEXT,
        "evidence_type": {"type": "string", "enum": ["synthetic"]},
        "pains": arr(
            obj(
                {
                    "pain": TEXT,
                    "evidence_quotes": arr(TEXT, minimum=1),
                    "severity": SCORE_1_5,
                    "frequency": SCORE_1_5,
                    "reach": SCORE_1_5,
                    "confidence": SCORE_1_5,
                    "priority_score": {"type": "integer", "minimum": 10, "maximum": 50},
                    "root_cause": TEXT,
                    "current_workarounds": STRING_LIST,
                    "desired_outcome": TEXT,
                    "related_jtbd": arr(TEXT, minimum=1, maximum=2),
                    "opportunity_notes": TEXT,
                }
            ),
            minimum=4,
            maximum=8,
        ),
    }
)


JTBD_SCHEMA = obj(
    {
        "segment": TEXT,
        "jtbd": arr(
            obj(
                {
                    "job_statement": TEXT,
                    "situation": TEXT,
                    "struggle": TEXT,
                    "desired_outcomes": arr(TEXT, minimum=4, maximum=7),
                    "forces": obj(
                        {
                            "pushes": arr(TEXT, minimum=2, maximum=5),
                            "pulls": arr(TEXT, minimum=2, maximum=5),
                            "anxieties": arr(TEXT, minimum=2, maximum=5),
                            "habits": arr(TEXT, minimum=2, maximum=5),
                        }
                    ),
                    "acceptance_criteria": arr(TEXT, minimum=3, maximum=6),
                    "moment_of_progress": TEXT,
                    "related_quotes": arr(TEXT, minimum=1, maximum=4),
                    "priority_score": {"type": "integer", "minimum": 0, "maximum": 100},
                }
            ),
            minimum=3,
            maximum=6,
        ),
    }
)


VPC_SCHEMA = obj(
    {
        "product": TEXT,
        "segment": TEXT,
        "customer_profile": obj(
            {
                "customer_jobs": obj(
                    {
                        "functional": STRING_LIST,
                        "social": STRING_LIST,
                        "emotional": STRING_LIST,
                    }
                ),
                "pains": STRING_LIST,
                "gains": STRING_LIST,
            }
        ),
        "value_map": obj(
            {
                "products_services": STRING_LIST,
                "pain_relievers": STRING_LIST,
                "gain_creators": STRING_LIST,
            }
        ),
    }
)


HYPOTHESES_SCHEMA = obj(
    {
        "hypotheses": arr(
            obj(
                {
                    "id": {"type": "integer", "minimum": 1},
                    "description": TEXT,
                    "rationale": TEXT,
                    "metric_to_validate": TEXT,
                    "expected_outcome": TEXT,
                    "reach": {"type": "integer", "minimum": 1},
                    "impact": {"type": "number", "enum": [0.25, 0.5, 1, 2, 3]},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "effort": {"type": "number", "minimum": 0.5},
                    "rationale_reach": TEXT,
                    "rationale_impact": TEXT,
                    "rationale_confidence": TEXT,
                    "rationale_effort": TEXT,
                }
            ),
            minimum=5,
            maximum=8,
        )
    }
)


LEAN_CANVAS_SCHEMA = obj(
    {
        "problem": arr(TEXT, minimum=1, maximum=3),
        "existing_alternatives": STRING_LIST,
        "solution": STRING_LIST,
        "unique_value_proposition": TEXT,
        "high_level_concept": TEXT,
        "unfair_advantage": TEXT,
        "customer_segments": STRING_LIST,
        "early_adopters": STRING_LIST,
        "key_metrics": STRING_LIST,
        "channels": STRING_LIST,
        "cost_structure": STRING_LIST,
        "revenue_streams": STRING_LIST,
        "assumptions_to_validate": STRING_LIST,
    }
)


def limited_schema(schema: JSONSchema, path: tuple[str, ...], maximum: int) -> JSONSchema:
    """Clone a schema and set maxItems at a nested property path."""

    result = deepcopy(schema)
    cursor: JSONSchema = result
    for part in path:
        cursor = cursor["properties"][part]
    cursor["maxItems"] = maximum
    return result
