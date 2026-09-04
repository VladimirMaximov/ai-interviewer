# Technical Research: Session-scoped Multi-agent Candidate Matching

## Decision 1: Use one durable orchestrator, not an agent mesh

**Decision**: `MultiAgentHarness` owns stage order, input manifests, validation, persistence, retry,
and resume. Agents never call one another and share no conversation thread.

**Rationale**: The workflow becomes reproducible and testable, context leakage is preventable, and a
provider failure does not require replaying successful stages.

**Alternatives considered**: Direct agent-to-agent handoff was rejected because hidden memory and
implicit retries make evidence lineage and isolation difficult to prove.

## Decision 2: Treat session memory as immutable references plus append-only artifacts

**Decision**: A session pins vacancy, resume, approved manager brief, policy, and compatibility
hashes. Derived results are immutable artifacts linked to operation runs.

**Rationale**: A later vacancy or resume edit cannot silently change the meaning of a completed
assessment or ranking.

**Alternatives considered**: A mutable JSON session document was rejected because concurrent stages
could overwrite history and old results could not be reproduced.

## Decision 3: Add a generic operation/run/artifact ledger

**Decision**: Use shared tables for all agent purposes and JSON payloads validated by strict domain
models. Ranking and human restrictions receive dedicated tables because they have query and authority
semantics different from agent output.

**Rationale**: Five agent purposes share identical idempotency, retry, hashing, and audit behavior;
copying these fields into purpose-specific tables creates avoidable inconsistency.

**Alternatives considered**: One table per agent purpose was rejected for the POC; event sourcing the
entire application was rejected as too broad.

## Decision 4: Reuse the FastAPI backend as the integration point

**Decision**: Extend `backend/app`, not the older WSGI `interview_platform` package.

**Rationale**: The backend already owns current vacancy/resume uploads, immutable versions,
candidate transcripts, recruiter authentication, manager-brief approval, SQLAlchemy, and Alembic.

**Alternatives considered**: Extending both applications would duplicate state and make one session
span two databases. Replacing existing routes would break compatibility.

## Decision 5: Run every semantic agent stage through an LLM

**Decision**: Define narrow protocols for resume relevance, question planning, answer assessment,
alternative matching, integrity checking, and candidate feedback, and implement all six with the
OpenAI Responses API and strict Structured Outputs. There is no heuristic runtime fallback. Tests
inject a fake Responses client at the adapter boundary.

**Rationale**: The product requires semantic interpretation at every agent step, while local
validation and injected clients keep the harness and safety properties independently testable. The
official Responses contract supports system instructions, bounded output tokens, stateless requests,
and JSON Schema/Pydantic structured output.

**Alternatives considered**: Deterministic production heuristics were rejected by product direction.
Live API calls in unit tests were rejected because they are slow, non-deterministic, and require
secrets; only test doubles may replace the LLM transport.

## Decision 6: Validate evidence before creating scoring artifacts

**Decision**: Numeric answer observations must cite an exact substring of the stored transcript and
must use the dimension declared by the question criterion. Missing evidence is a null observation.

**Rationale**: This prevents hallucinated quotes, resume-based performance scores, and accidental
cross-dimension score propagation.

**Alternatives considered**: Trusting provider JSON or accepting paraphrases was rejected because a
reviewer could not reliably verify the result.

## Decision 7: Compute profiles, eligibility, and rankings deterministically

**Decision**: Agents emit observations. Application code averages non-null values, exposes coverage,
applies the pinned strong-pool policy, and orders compatible profiles.

**Rationale**: Repeated inputs produce the same output, thresholds are reviewable, and scoring rules
can be calibrated without prompt changes.

**Alternatives considered**: Asking an LLM for a final score or rank was rejected because arithmetic
and cohort ordering must be deterministic.

## Decision 8: Separate current-vacancy ranking from cross-vacancy recommendations

**Decision**: Ranking is a cohort operation scoped to one vacancy compatibility key. Alternative
matching compares one eligible candidate profile with active vacancies and never creates an
application automatically.

**Rationale**: A candidate can be a poor fit for one role and strong for another. Conversely, an
under-evidenced profile should not create noisy talent-pool recommendations.

**Alternatives considered**: One global candidate score was rejected because competence is
criterion- and vacancy-dependent.

## Decision 9: Model suspected dishonesty as an integrity observation

**Decision**: Agents may emit `unverified_claim`, `contradiction_detected`, or
`manual_integrity_review`, with evidence on both sides. They cannot emit blacklist or restriction
decisions.

**Rationale**: Resume/answer inconsistency does not prove intent and may result from transcription,
ambiguity, memory, or question framing.

**Alternatives considered**: Automatic blacklisting was rejected as incompatible with repository
human-decision rules and too risky for an uncalibrated model.

## Decision 10: Store human restrictions as append-only decisions

**Decision**: A recruiter-authenticated action may append `verified_misrepresentation`,
`restricted`, `blacklisted`, or `cleared`, with reason, evidence references, optional expiry, and a
superseded-decision link.

**Rationale**: Authority, reason, effective state, and reversal remain auditable without modifying
agent evidence or scores.

**Alternatives considered**: A mutable boolean on the candidate was rejected because it loses who,
why, and when, and cannot represent expiry or correction.
