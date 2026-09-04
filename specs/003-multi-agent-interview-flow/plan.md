# Implementation Plan: Session-scoped Multi-agent Candidate Matching

**Branch**: `003-multi-agent-interview-flow` | **Date**: 2026-09-04 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/003-multi-agent-interview-flow/spec.md`

## Summary

Extend the current FastAPI backend with one durable `MultiAgentHarness` that owns isolated session
memory and runs specialized, schema-constrained agents. The first complete vertical slice pins the
vacancy, latest resume, optional approved manager brief, criteria policy, and interview responses;
produces resume-experience matches and a traceable question plan; assesses confirmed answer text by
independent dimensions; deterministically builds a candidate profile and vacancy ranking; proposes
alternative active vacancies only for eligible strong profiles; and records consistency flags which
can become restrictions only through a separate human endpoint.

The implementation uses generic append-only operation/run/artifact persistence instead of one table
per model output. Agent adapters emit observations and explanations only. Hashing, idempotency,
scale validation, evidence validation, aggregation, ranking, eligibility, and restriction effects
remain deterministic application logic.

## Technical Context

**Language/Version**: Python 3.12+

**Primary Dependencies**: FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, OpenAI Python SDK Responses
API with Structured Outputs; injectable fake Responses client only inside tests

**Storage**: Existing PostgreSQL schema in production and SQLite in unit/integration tests; additive
Alembic migration `005_multi_agent_harness.py`

**Testing**: Standard-library `unittest`, FastAPI `TestClient`, in-memory SQLite, compileall, and
existing backend/root regression suites

**Target Platform**: Existing local Linux/macOS API service

**Project Type**: Web service with modular domain, service, adapter, model, and API layers

**Performance Goals**: Stored recruiter projections under two seconds for 1,000 synthetic completed
profiles; confirmed-answer persistence does not wait for model execution; ranking is deterministic
and database bounded

**Constraints**: Preserve current candidate, vacancy, resume, transcript, and manager endpoints;
never score sensitive traits; never treat resume text as interview evidence; missing evidence is
nullable; no automatic hiring transition or restriction; deterministic calculations only; all
fixtures synthetic; every semantic agent stage uses an LLM in runtime; no provider/network
requirement in tests because the Responses client is injected

**Scale/Scope**: One organization, hundreds of active vacancies, up to 1,000 completed profiles per
vacancy cohort, five agent purposes, and append-only audit history

## Constitution Check

The repository constitution is an unratified placeholder, so `AGENTS.md` provides the active gates.

- **Evidence classification — PASS**: vacancy requirements, resume claims, answer evidence, agent
  observations, deterministic scores, and human restrictions are separate artifacts.
- **Evidence-first — PASS**: every numeric answer observation must cite an exact transcript span;
  missing evidence is `null` with `insufficient_information`.
- **No automatic rejection — PASS**: ranking and integrity stages never mutate invitation status;
  only a recruiter-authenticated human action creates or clears a restriction.
- **No sensitive-trait scoring — PASS**: purpose contexts and validators exclude protected and
  non-work-related traits.
- **Deterministic scoring — PASS**: application code validates labels, aggregates values, calculates
  coverage, orders rankings, and applies strong-pool eligibility.
- **Privacy and isolation — PASS**: one session is bound to one invitation/vacancy; agent contexts
  never include other candidates.
- **Testing — PASS**: new parsing, validation, idempotency, retry, isolation, scoring, matching,
  ranking, and restriction behavior receives regression coverage.
- **Simplicity — PASS**: one orchestrator and one generic artifact ledger extend the existing
  modular monolith; no distributed agent mesh or new runtime service is introduced.

Post-design re-check: PASS. Human restriction authority and append-only history are explicit in the
data model and API contract.

## Architecture

```text
vacancy + latest resume + optional approved brief + policy + own transcripts
                                  |
                                  v
                         MultiAgentHarness
                                  |
                    AgentSession + input snapshot
                                  |
             +--------------------+--------------------+
             |                    |                    |
             v                    v                    v
     resume_relevance       question_plan       answer_assessment(s)
             |                    |                    |
             +--------------------+--------------------+
                                  v
                    deterministic candidate profile
                                  |
                +-----------------+------------------+
                |                 |                  |
                v                 v                  v
         vacancy ranking   alternative matcher   integrity checker
                                                    |
                                             observation only
                                                    |
                                             human review API
                                                    |
                                           append-only restriction
```

Every agent call is represented by `AgentOperation` and one or more `AgentRun` attempts. A validated
successful output becomes an immutable `AgentArtifact`; invalid output is audited but never
materialized. The harness reads its own persisted artifacts, so a process restart resumes instead of
replaying successful stages.

## Agent Purposes and Boundaries

| Purpose | Allowed input | Validated output | Excluded |
|---|---|---|---|
| `resume_relevance` | pinned vacancy, resume, approved brief | LLM claims and experience-to-requirement matches | answers, other candidates, sensitive traits |
| `question_plan` | vacancy, approved brief, resume analysis | fixed baseline plus bounded claim-verification questions | new criteria, ranking, decisions |
| `answer_assessment` | one stored transcript, one question, applicable criteria | independent criterion observations with exact evidence | other candidates, hiring decisions |
| `alternative_vacancy_match` | completed evidence profile, active vacancy catalog | explanatory candidate-vacancy observations | cohort rank, application creation |
| `integrity_check` | resume claims and the candidate's own stored answers | consistency observations and clarification prompts | `blacklisted`, `restricted`, rejection |

All five roles are implemented by an OpenAI Responses adapter using a separate system instruction
and strict Pydantic Structured Output type for each purpose. The adapter is stateless (`store=False`)
and receives the harness-built session manifest on every call. Tests inject a fake Responses client;
there is no heuristic runtime fallback when credentials or the provider are unavailable.

## Deterministic Rules

- Valid signed values are exactly `-1`, `-0.5`, `0`, `0.5`, `1`, or `null` for insufficient
  information.
- A numeric observation requires an exact substring of the stored answer. Resume excerpts cannot be
  cited as proof of interview performance.
- Criterion value is the arithmetic mean of non-null observations for that criterion.
- Dimension value is the arithmetic mean of its assessed criterion values. Coverage is assessed
  criteria divided by applicable criteria and is always reported separately.
- Overall readiness is the mean of assessed dimension values. The POC strong-pool policy requires
  readiness at least `0.25`, coverage at least `0.50`, no material integrity review, and no active
  human restriction. The policy identifier and thresholds are pinned in the session.
- Vacancy ranking includes only completed profiles with the same compatibility key. Order is
  descending overall score, descending coverage, then ascending stable session ID.
- Ranking loads profiles and current human restrictions in bounded batch queries; a synthetic
  1,000-profile regression guards the two-second target and one-to-one session isolation.
- Alternative fit is proposed by the LLM only from candidate evidence and active vacancy work
  requirements. The harness validates its evidence references and target vacancy; deterministic
  policy filters low-fit or ineligible results from the published pool.

## API Surface

Recruiter-authenticated endpoints are additive under `/recruiter`:

- create/get an agent session for a vacancy application;
- run resume analysis and question planning;
- assess a stored completed transcript with declared question criteria;
- finalize profile, integrity analysis, and alternative matches;
- retrieve the session projection and vacancy ranking;
- append or supersede a human restriction decision.

The candidate API receives no scores, rankings, integrity observations, or restrictions in this
increment. Existing upload and transcript endpoints remain unchanged.

## Project Structure

### Documentation (this feature)

```text
specs/003-multi-agent-interview-flow/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── openapi.yaml
│   └── agent-output.schema.json
└── tasks.md
```

### Source Code (repository root)

```text
backend/app/
├── api/
│   └── multi_agent.py
├── adapters/
│   └── openai_interview_agents.py
├── domain/
│   └── multi_agent.py
├── models/
│   └── multi_agent.py
├── services/
│   └── multi_agent_harness.py
├── database.py
└── main.py

backend/alembic/versions/
└── 005_multi_agent_harness.py

backend/tests/
├── unit/
│   └── test_multi_agent_harness.py
└── integration/
    ├── test_multi_agent_api.py
    └── test_multi_agent_migration.py
```

**Structure Decision**: Implement in `backend/`, the active FastAPI application which already owns
vacancy/resume context and manager-brief approval. The legacy `interview_platform/` assessment path
is not modified or mixed into new ranking cohorts.

## Delivery Strategy

1. Add strict domain contracts and additive persistence.
2. Implement session creation, purpose contexts, idempotent operation/run execution, and artifact
   validation.
3. Add OpenAI Responses agent adapters and resume/question stages.
4. Add answer assessment plus profile aggregation and ranking.
5. Add alternative matching, integrity observations, and human restriction history.
6. Expose recruiter endpoints, document the flow, and run all repository gates.

## Complexity Tracking

No constitution violations require justification.
