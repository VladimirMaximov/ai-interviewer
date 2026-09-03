# Output contract

Use this contract when the task requires saved artifacts or machine-readable JSON. A single
`result.json` should have these top-level fields:

```text
metadata
  direction, model, created_at, completed_at, evidence_notice
research
  direction, products[]
products[]
  candidate, page, description, segments[], segment_analyses[]
```

Each `research.products[]` item contains `name`, `url`, `what_it_sells`,
`commercial_evidence`, and `source_urls[]`. Preserve `url` in every downstream product context.

Each `segment_analyses[]` item contains:

```text
segment
icp
interview
pain_map
jtbd
value_proposition_canvas
hypotheses[]
best_hypothesis
lean_canvas
```

## Evidence labels

An interview must contain `evidence_type`, whose value is either `real` or `synthetic`. If it is
synthetic, include a `validation_warning`. Pain Map and JTBD quotes inherit that label. Never mix
real and synthetic quotes without a per-quote evidence label.

## Pain Map

Each pain contains:

```json
{
  "pain": "Specific user-language pain",
  "evidence_quotes": ["Q3/A3: short quote"],
  "severity": 1,
  "frequency": 1,
  "reach": 1,
  "confidence": 1,
  "priority_score": 10,
  "root_cause": "Why it happens",
  "current_workarounds": ["Current workaround"],
  "desired_outcome": "What good looks like",
  "related_jtbd": ["Short job"],
  "opportunity_notes": "Possible response"
}
```

All component scores are integers from 1 through 5. Recalculate `priority_score` rather than
trusting generated arithmetic.

## JTBD

Each JTBD contains `job_statement`, `situation`, `struggle`, `desired_outcomes[]`, `forces`
(`pushes[]`, `pulls[]`, `anxieties[]`, `habits[]`), `acceptance_criteria[]`,
`moment_of_progress`, `related_quotes[]`, and `priority_score` from 0 through 100.

## Hypotheses and RICE

Each hypothesis contains `id`, `description`, `rationale`, `metric_to_validate`,
`expected_outcome`, `reach`, `impact`, `confidence`, `effort`, rationales for the four inputs,
and calculated `rice_score`. Impact is one of `0.25`, `0.5`, `1`, `2`, or `3`; effort is at
least `0.5` person-weeks in `0.5` increments. State the period and any reach assumptions.

## Lean Canvas

Use these fields: `problem[]`, `existing_alternatives[]`, `solution[]`,
`unique_value_proposition`, `high_level_concept`, `unfair_advantage`, `customer_segments[]`,
`early_adopters[]`, `key_metrics[]`, `channels[]`, `cost_structure[]`, `revenue_streams[]`, and
`assumptions_to_validate[]`.
