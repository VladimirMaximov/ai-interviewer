# Implementation Plan: Vacancy-aware Candidate Assessment and Feedback

**Branch**: `002-vacancy-fit-assessment` | **Date**: 2026-09-03 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/002-vacancy-fit-assessment/spec.md`

## Summary

Extend the existing asynchronous-interview modular monolith with versioned corporate competency
frameworks, manager-approved vacancy profiles, immutable assessment-context snapshots,
criterion-level evidence-based assessments, deterministic per-dimension aggregation, compatible-only
ranking, separate human decisions, and a two-stage candidate-feedback timeline.

The central architectural rule is that vacancy-specific "agent memory" is not ambient conversation
history. It is a bounded context assembled from approved, versioned records for one operation and one
vacancy. Corporate competence, vacancy fit, evidence sufficiency, integrity events, human decisions,
and candidate-visible feedback stay separate throughout storage, business logic, and projections.

## Technical Context

**Language/Version**: Python 3.12+

**Primary Dependencies**: Python standard library for the runnable POC (`dataclasses`, `enum`,
`hashlib`, `json`, `sqlite3`, `wsgiref`); provider and document-processing integrations remain behind
application-owned protocols

**Storage**: SQLite with explicit forward migrations and repositories for framework, vacancy,
assessment, ranking, decision, and feedback aggregates

**Testing**: `unittest` for domain invariants, schema/migration behavior, context isolation,
deterministic aggregation, API contracts, access projections, retry/idempotency, and end-to-end flows

**Target Platform**: Local macOS/Linux process for the POC; deployable behind a production WSGI
server and production database adapter in a later phase

**Project Type**: Modular monolith web application and JSON API

**Performance Goals**: Stored manager/candidate reads under 250 ms p95 for 1,000 synthetic interviews;
context-snapshot assembly under 50 ms p95; deterministic scoring and ranking of 1,000 compatible
candidates under 1 second, excluding external model or transcription latency

**Constraints**: Preserve current candidate and manager routes during migration; no third-party
runtime dependency in the first slice; no real candidate PII/media committed; no automatic hiring
decision; content-only scoring; every criterion result must validate against stored evidence;
snake_case external fields; deterministic aggregation and ranking

**Scale/Scope**: One organization, the 13 role/profile families represented in the source framework,
up to 100 active vacancy versions, 1,000 synthetic interviews per vacancy for deterministic ranking
tests, two feedback stages, and replaceable AI/document/speech adapters

## Constitution Check

The repository constitution remains an unratified placeholder and defines no enforceable gates. The
repository `AGENTS.md` acts as the governing quality gate:

- **Evidence classification**: PASS - source fragments, system suggestions, criterion evidence,
  missing evidence, and human decisions are distinct records with provenance.
- **Evidence-first assessment**: PASS - every numeric/ordinal criterion result requires a validated
  quote or time span; otherwise it is `insufficient_information` outside the score scale.
- **Separated decisions**: PASS - assessment output, recruiter decision, technical-expert decision,
  and hiring-manager decision use different entities and contracts.
- **No automatic rejection or sensitive-trait scoring**: PASS - aggregation and ranking never mutate
  hiring state; forbidden signal categories are rejected at vacancy-profile approval.
- **Deterministic scoring**: PASS - only application code aggregates weights, coverage, and ranks;
  generative adapters cannot calculate or overwrite final summaries.
- **Privacy**: PASS - the POC uses synthetic records, scoped context, hashed source content, and
  candidate-safe projections. Raw tokens, PII, recordings, and transcripts are not committed.
- **Regression coverage**: PASS by design - success, malformed input, incompatible versions, retry,
  resume, migration, and publication history are explicit test groups.
- **Simplicity**: PASS - the design extends the existing modular monolith and repository boundary;
  it adds no deployable service or mandatory external runtime dependency.

Post-design re-check: PASS. The data model and contracts preserve all gates. No justified exception
or complexity waiver is required.

## Architecture

```text
Manager authoring
  text / defaults / file / speech transcript
                 |
                 v
      Context Source Adapters
                 |
                 v
Vacancy Profile Service -- draft -> validate -> approve immutable version
                 |                         |
                 |                         +--> question/rubric coverage
                 v
      Assessment Context Snapshot <---- corporate framework version
                 |
                 +--> Question generation context
                 +--> Criterion assessment context
                 +--> Ranking policy context
                 +--> Candidate-feedback policy context
                                      |
Candidate answers -> Evidence validation -> Criterion Assessments
                                      |
                      deterministic summaries
                         /          |          \
          corporate competency   vacancy fit   evidence coverage
                         \          |          /
                          compatible ranking
                                  |
                  recruiter / expert / manager decisions
                                  |
             draft feedback -> human publish -> later feedback entry
```

Dependency direction remains `web -> application -> domain`. Infrastructure implements repositories
and external-capability ports. The context assembler is an application service: it loads only the IDs
pinned by an interview snapshot and emits immutable data-transfer objects to adapters. No adapter can
query arbitrary vacancies or write domain state directly.

## Component Responsibilities

### Domain

- `competencies`: framework versions, role profiles, competency anchors, publication rules.
- `vacancies`: vacancy aggregate, source provenance, criteria, profile-version approval, forbidden
  criteria, question coverage, and version immutability.
- `assessment`: context snapshots, runs, criterion results, evidence validation, independent dimension
  summaries, and run state transitions.
- `ranking`: ranking-policy validation, compatibility key, coverage floor, stable ordering, tied ranks,
  and immutable ranking snapshots.
- `decisions`: append-only human decisions owned by recruiter, technical expert, or hiring manager.
- `feedback`: staged drafts, revisions, publication transitions, correction links, and candidate-safe
  fields.
- `interview`: existing invitation/answer lifecycle, augmented only with vacancy and context-snapshot
  references; it does not absorb assessment or vacancy rules.

### Application

- `FrameworkService` loads and publishes normalized framework versions.
- `VacancyProfileService` creates vacancies, ingests context sources, requests a structured draft,
  validates edits, and approves versions.
- `AssessmentContextAssembler` resolves exact versions and produces task-specific bounded context.
- `AssessmentService` creates idempotent runs, invokes a criterion evaluator, validates its evidence,
  and asks the deterministic aggregator to create summaries.
- `RankingService` builds an immutable snapshot from compatible completed runs and a pre-published
  policy.
- `DecisionService` records role-scoped human decisions without changing assessments.
- `FeedbackService` creates the preliminary draft, accepts human edits, publishes candidate-safe
  revisions, and adds the post-review entry.

Application-owned ports isolate:

- context extraction from uploaded content;
- speech-to-text output acquisition;
- vacancy-profile draft generation;
- criterion-level assessment;
- candidate-feedback draft generation;
- repositories, clock, identifiers, and audit-event sink.

### Infrastructure and delivery

- SQLite adapters persist each aggregate transactionally and apply numbered forward migrations.
- Initial source adapters accept direct text, UTF-8 `.txt`/`.md`, and existing speech transcripts;
  unsupported formats return a typed result rather than partial content.
- Deterministic fake drafting/evaluation adapters support the full synthetic POC and frozen tests.
- The WSGI layer exposes manager authoring, assessment, ranking, decision, and feedback routes while
  reusing current manager authentication and candidate token access.
- Presenters build distinct manager and candidate projections; candidate serializers never receive
  internal ranking or decision objects.

## Vacancy Context and Agent-Memory Assembly

The authoritative layers, from least to most specific, are:

1. code-owned safety and output policy;
2. one published corporate-framework version and selected role/level anchors;
3. one approved vacancy-profile version and its source provenance;
4. one approved question/rubric version and ranking/feedback policies;
5. candidate evidence for the current interview only.

`AssessmentContextSnapshot` stores references and content hashes for layers 2-4 when an interview is
created. Each operation requests only its required view:

- profile drafting receives framework anchors plus manager context sources, but no candidates;
- question generation receives the approved profile, but no candidate answers;
- criterion assessment receives the pinned rubric and current candidate evidence, but no other
  candidates or human decision;
- ranking receives validated immutable summaries, not raw answers or model prompts;
- feedback drafting receives criterion results and candidate-safe policy, not rank or decisions.

The context assembler wraps manager/file content as untrusted data and validates the adapter output
against a closed schema. Prompt/cache/audit metadata includes operation kind, adapter identity,
framework version, vacancy-profile version, rubric version, snapshot hash, and output hash. A manager
edit never mutates an existing snapshot.

## Assessment and Ranking Rules

The evaluator emits one of four anchored labels or `insufficient_information` for every applicable
criterion. Domain validation rejects a numeric label without evidence that is a substring/time span
of a stored answer. Counter-evidence uses the same validation rule.

For dimension `d`:

```text
assessed_weight(d) = sum(weight of applicable criteria with numeric labels)
applicable_weight(d) = sum(weight of all applicable criteria)
coverage(d) = assessed_weight(d) / applicable_weight(d)
score(d) = sum(weight * ordinal_value) / (3 * assessed_weight(d)) * 100
```

`score(d)` is absent when `assessed_weight(d) = 0`. Values are stored at full precision and displayed
using the ranking policy's declared precision. Corporate and vacancy-fit formulas run separately and
produce separate summaries.

Ranking requires an exact compatibility key composed of vacancy ID and all relevant policy/version
IDs. Below the evidence-coverage floor, a run goes to `additional_review` without ordinal position.
Above the floor, the published policy declares primary and optional secondary dimensions. Equal
display-precision values share a rank. The service never writes a human decision.

## Feedback Lifecycle

```text
assessment completed
    -> post_async_assessment / draft / ai_assisted
    -> reviewer edits or rejects draft
    -> published (immutable candidate-visible entry)

human or later technical review completed
    -> post_human_review / draft / human_authored
    -> published (new timeline entry)

published error discovered
    -> corrective draft links to prior publication
    -> corrective publication; prior entry remains in history
```

Each revision has one audience projection. Candidate-safe fields are assessment scope, strengths,
growth areas, evidence gaps, limitations, and next steps. Internal notes, criterion weights,
vacancy-fit totals, ranking, integrity events, and decisions never enter the candidate projection.

## Persistence and Migration Strategy

The current schema creates `interviews`, `questions`, `answers`, a single `feedback` row per interview,
and `evidence`. Introduce a migration ledger and make changes in additive phases:

1. Add framework, role-profile, vacancy, context-source, profile-version, criterion, policy, and
   context-snapshot tables. Add nullable `vacancy_id` and `assessment_context_snapshot_id` to legacy
   interviews so existing rows continue to load.
2. Add assessment-run, criterion-assessment, assessment-evidence, dimension-summary, ranking-policy,
   ranking-snapshot, ranking-entry, human-decision, audit-event, feedback-entry, and feedback-revision
   tables.
3. Adapt the current manager-authored `feedback` row on read as a `post_human_review` legacy entry.
   New writes use the new feedback tables. A later explicit migration can copy old rows after the new
   contract has regression coverage.
4. Require vacancy/context references only for interviews created by the new vacancy route. Keep the
   existing direct interview-creation route as a deprecated synthetic-demo path until callers move.

Every profile approval, assessment completion, ranking creation, decision append, and feedback
publication is one transaction. Idempotency keys protect adapter retries and repeated POSTs.

## Project Structure

### Documentation (this feature)

```text
specs/002-vacancy-fit-assessment/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── checklists/
│   └── requirements.md
└── contracts/
    └── openapi.yaml
```

### Source Code (repository root)

```text
interview_platform/
├── data/
│   └── competency_framework.v1.json
├── domain/
│   ├── models.py                 # existing interview lifecycle during migration
│   ├── competencies.py
│   ├── vacancies.py
│   ├── assessment.py
│   ├── ranking.py
│   ├── decisions.py
│   └── feedback.py
├── application/
│   ├── ports.py
│   ├── services.py              # existing interview use cases
│   ├── vacancy_services.py
│   ├── assessment_services.py
│   ├── context.py
│   ├── ranking_services.py
│   └── feedback_services.py
├── infrastructure/
│   ├── migrations/
│   │   ├── 001_existing_poc.sql
│   │   └── 002_vacancy_assessment.sql
│   ├── sqlite_repository.py     # existing compatibility adapter
│   ├── sqlite_vacancies.py
│   ├── sqlite_assessments.py
│   ├── source_extractors.py
│   └── evaluation_stubs.py
└── web/
    ├── app.py
    ├── presenters.py
    └── schemas.py

tests/
├── fixtures/
│   ├── competency_framework.v1.json
│   └── synthetic_assessments.json
├── test_competency_framework.py
├── test_vacancy_profile.py
├── test_context_isolation.py
├── test_assessment.py
├── test_ranking.py
├── test_decisions.py
├── test_feedback_timeline.py
├── test_assessment_repository.py
├── test_vacancy_assessment_api.py
└── test_interview_architecture.py
```

**Structure Decision**: Keep one deployable Python package and extend the established inward-facing
boundaries. Split new domain concepts into small modules because vacancy approval, assessment,
ranking, decisions, and feedback have different invariants and lifecycles. Keep legacy interview code
operational while routes and persistence migrate incrementally.

## Validation Strategy

- Normalize every source-deck role and anchor, verify stable IDs, and ensure the loader rejects
  duplicate competencies, invalid role/level pairs, or missing source provenance.
- Test vacancy drafts from defaults, phrases, pasted text, `.txt`/`.md`, speech transcript, empty and
  malformed input, prompt-injection-like content, duplicate criteria, prohibited traits, and missing
  question coverage.
- Freeze an interview snapshot, publish new framework/vacancy versions, and prove the existing
  snapshot and evaluation output do not change.
- Evaluate the same answer against two vacancy profiles and prove corporate competency results are
  identical while only vacancy-fit results differ.
- Test evidence substring/time-span validation, counter-evidence, `insufficient_information`, retry,
  partial adapter output, and resumption of a pending assessment run.
- Recalculate aggregates and ranking repeatedly, randomize input order, and prove identical summaries,
  ties, additional-review grouping, and compatibility rejection.
- Prove assessment output and integrity events cannot call decision transitions.
- Publish both feedback stages, create a correction, and assert append-only history plus strict
  candidate/internal field separation.
- Run the current test suite unchanged to protect the candidate journey and legacy manager flow.

## Complexity Tracking

No constitution or repository-rule violations require justification. The additional domain modules
and repositories represent distinct state machines inside the existing modular monolith, not new
deployable systems.
