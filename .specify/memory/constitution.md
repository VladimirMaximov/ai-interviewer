<!--
Sync Impact Report
- Version change: 1.0.0 → 1.1.0
- Modified principles: none
- Added sections: FastAPI backend and PostgreSQL persistence baseline
- Removed sections: none
- Follow-up TODOs: none
-->

# AI Interviewer Constitution

## Core Principles

### I. Evidence-First Candidate Evaluation

Every candidate-related score, recommendation, or explanation MUST cite concrete transcript
quotes or timestamps. Missing evidence MUST be represented explicitly. AI recommendations,
recruiter decisions, and hiring-manager decisions MUST remain distinct. This keeps decisions
auditable and prevents unsupported inference.

### II. Human Oversight and Fair Evaluation

The system MUST NOT automatically reject candidates or score appearance, accent, emotion, or
voice confidence. Simulated interviews MUST be labelled `synthetic` and MUST NOT be presented as
customer validation. Product and evaluation features MUST preserve meaningful human review.

### III. Privacy and Data Minimization

Candidate PII, recordings, transcripts, and secrets MUST NOT be committed to the repository.
Features handling interview data MUST minimize collection and persistence, clearly separate
operational data from generated reports, and call out their privacy impact in review.

### IV. Deterministic, Tested Core Logic

Pain, RICE, scoring, ranking, parsing, schema, and checkpoint logic MUST be deterministic; an
LLM MUST NOT calculate Pain or RICE scores. Every such change MUST add regression coverage for
success, malformed input, retry, and resume paths as applicable.

### V. Evidence Integrity and Reproducibility

Research artifacts MUST distinguish verified facts, vendor claims, external observations, and
assumptions, preserve current official-source URLs, and describe evidence gaps. Provider or model
changes MUST pass the frozen evaluation before adoption.

## Domain & Data Safeguards

Python 3.12 or newer is required. The backend MUST use FastAPI. Where durable relational
persistence is required, PostgreSQL is the approved default; schemas and migrations MUST preserve
the privacy and evidence rules above. The frontend technology remains intentionally undecided and
MUST be chosen in the feature plan based on the call experience, browser support, accessibility,
and operational simplicity. Public interfaces use type hints and modules keep a single
responsibility. Machine-readable fields use `snake_case`; research files use lowercase kebab-case.
Competitor evidence belongs in `research/`, product decisions and machine-readable outputs in
`deliverables/ai-technical-interview/`, and stakeholder notes in `interview/`.

## Development Workflow & Quality Gates

Each material feature starts with a Spec Kit specification, then a plan and dependency-ordered
tasks. Before review, run `python -m unittest discover -s tests -v` and
`python -m compileall -q product_engineering`. Pull requests MUST identify the affected interview
stage, evidence sources, validation commands, schema or model changes, privacy impact, and known
evaluation gaps. Commits use short imperative prefixes such as `feat:`, `fix:`, `test:`, or
`docs:`.

## Governance

This constitution governs project delivery and complements `AGENTS.md`; where requirements
conflict, the stricter privacy, fairness, evidence, or testing rule applies. Amendments MUST be
documented in this file with a Sync Impact Report and a semantic version increment: MAJOR for
backward-incompatible principle changes, MINOR for new or materially expanded guidance, and PATCH
for clarifications. Every feature review MUST check compliance with the core principles and record
any approved exception together with its rationale and remediation plan.

**Version**: 1.1.0 | **Ratified**: 2026-09-03 | **Last Amended**: 2026-09-03
