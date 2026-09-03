# Tasks: Vacancy-aware Candidate Assessment and Feedback

**Input**: Design documents from `/specs/002-vacancy-fit-assessment/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/openapi.yaml`, `quickstart.md`

**Tests**: Regression and story-specific tests are required by the repository guidelines and feature specification.

**Organization**: Tasks are grouped by user story and executed test-first inside each story.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Prepare stable reference data and migration structure without breaking the existing POC.

- [X] T001 Add the versioned normalized Napoleon IT framework dataset in `interview_platform/data/competency_framework.v1.json`
- [X] T002 Create the migration package and migration ledger bootstrap in `interview_platform/infrastructure/migrations/` and `interview_platform/infrastructure/migration_runner.py`
- [X] T003 [P] Add vacancy-assessment configuration limits in `interview_platform/config.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Add shared domain values, repository contracts, persistence, and composition required by every story.

- [X] T004 Add shared actor, provenance, audit, hashing, and validation primitives in `interview_platform/domain/hiring.py`
- [X] T005 Add hiring repository and adapter protocols in `interview_platform/application/ports.py`
- [X] T006 Implement the additive SQLite hiring schema and transactional repository in `interview_platform/infrastructure/sqlite_hiring_repository.py`
- [X] T007 Wire an optional hiring service into the composition root and web application in `interview_platform/__main__.py` and `interview_platform/web/app.py`
- [X] T008 [P] Extend architecture-boundary regression coverage in `tests/test_interview_architecture.py`

**Checkpoint**: The existing interview flow still works and new hiring components obey inward dependencies.

---

## Phase 3: User Story 1 - Manager creates an approved vacancy profile (Priority: P1) MVP

**Goal**: Let a manager create a vacancy from the corporate framework, add trusted-provenance text/file/speech-transcript sources, review structured criteria, and approve an immutable profile.

**Independent Test**: Create and approve one Software Engineer vacancy profile from text and Markdown; prohibited or uncovered criteria fail approval, and later edits create a new version.

### Tests for User Story 1

- [X] T009 [P] [US1] Add framework loading and role/anchor validation tests in `tests/test_competency_framework.py`
- [X] T010 [P] [US1] Add vacancy draft, provenance, approval, and versioning tests in `tests/test_vacancy_profile.py`
- [X] T011 [P] [US1] Add manager vacancy API and file-source tests in `tests/test_vacancy_assessment_api.py`

### Implementation for User Story 1

- [X] T012 [US1] Implement framework, vacancy source, profile, criterion, and approval models in `interview_platform/domain/competencies.py` and `interview_platform/domain/vacancies.py`
- [X] T013 [US1] Implement UTF-8 text/Markdown extraction and input classification in `interview_platform/infrastructure/source_extractors.py`
- [X] T014 [US1] Implement vacancy profile drafting, validation, versioning, and approval use cases in `interview_platform/application/vacancy_services.py`
- [X] T015 [US1] Persist frameworks, vacancies, sources, fragments, profile versions, criteria, questions, policies, and snapshots in `interview_platform/infrastructure/sqlite_hiring_repository.py`
- [X] T016 [US1] Implement manager vacancy JSON endpoints and multipart parsing in `interview_platform/web/app.py`
- [X] T017 [US1] Implement manager vacancy list, authoring, review, and approval pages in `interview_platform/web/presenters.py`

**Checkpoint**: A manager can create and approve a versioned vacancy context through the browser or API.

---

## Phase 4: User Story 2 - Candidate receives a multidimensional assessment (Priority: P2)

**Goal**: Pin vacancy context to an interview and produce evidence-backed corporate-competency and vacancy-fit results with separate coverage/confidence.

**Independent Test**: Assess the same synthetic answer under two vacancy profiles; corporate results remain identical while vacancy-fit results differ only by approved criteria.

### Tests for User Story 2

- [X] T018 [P] [US2] Add context immutability and cross-vacancy isolation tests in `tests/test_context_isolation.py`
- [X] T019 [P] [US2] Add criterion evidence, missing-information, aggregation, retry, and resume tests in `tests/test_assessment.py`
- [X] T020 [P] [US2] Add assessment persistence round-trip tests in `tests/test_assessment_repository.py`

### Implementation for User Story 2

- [X] T021 [US2] Implement assessment snapshots, runs, criterion evidence, and deterministic summaries in `interview_platform/domain/assessment.py`
- [X] T022 [US2] Implement bounded context assembly and deterministic evidence evaluator in `interview_platform/application/context.py` and `interview_platform/infrastructure/evaluation_stubs.py`
- [X] T023 [US2] Implement idempotent assessment orchestration in `interview_platform/application/assessment_services.py`
- [X] T024 [US2] Persist snapshots, runs, criterion results, evidence, summaries, and integrity signals in `interview_platform/infrastructure/sqlite_hiring_repository.py`
- [X] T025 [US2] Implement assessment API endpoints and manager evidence cards in `interview_platform/web/app.py` and `interview_platform/web/presenters.py`

**Checkpoint**: Completed interviews have reproducible, independently stored assessment dimensions.

---

## Phase 5: User Story 3 - Recruiter compares candidates within one vacancy (Priority: P3)

**Goal**: Rank only compatible completed assessments, group low-evidence runs for review, and store human decisions separately.

**Independent Test**: Rank three compatible synthetic candidates deterministically, reject an incompatible run, preserve ties, and append disagreeing human decisions without changing scores.

### Tests for User Story 3

- [X] T026 [P] [US3] Add deterministic ranking, compatibility, tie, and coverage-floor tests in `tests/test_ranking.py`
- [X] T027 [P] [US3] Add append-only role-separated decision tests in `tests/test_decisions.py`

### Implementation for User Story 3

- [X] T028 [US3] Implement ranking policies, snapshots, entries, and compatibility keys in `interview_platform/domain/ranking.py`
- [X] T029 [US3] Implement append-only role-separated decisions in `interview_platform/domain/decisions.py`
- [X] T030 [US3] Implement ranking and decision use cases in `interview_platform/application/ranking_services.py`
- [X] T031 [US3] Persist ranking snapshots, entries, and human decisions in `interview_platform/infrastructure/sqlite_hiring_repository.py`
- [X] T032 [US3] Implement ranking and decision API/UI flows in `interview_platform/web/app.py` and `interview_platform/web/presenters.py`

**Checkpoint**: Staff can explain ordering and still make an independent human decision.

---

## Phase 6: User Story 4 - Candidate feedback evolves across stages (Priority: P4)

**Goal**: Create preliminary and human-review feedback entries with append-only revisions and a strict candidate-safe timeline.

**Independent Test**: Publish both stages and a correction; the candidate sees only published safe fields in order while internal fields and previous versions remain protected.

### Tests for User Story 4

- [X] T033 [P] [US4] Add feedback lifecycle, correction, and candidate-projection tests in `tests/test_feedback_timeline.py`
- [X] T034 [P] [US4] Extend HTTP contract tests for manager publication and candidate timeline in `tests/test_vacancy_assessment_api.py`

### Implementation for User Story 4

- [X] T035 [US4] Implement feedback entries, revisions, evidence links, and publication invariants in `interview_platform/domain/feedback.py`
- [X] T036 [US4] Implement staged feedback drafting and publication use cases in `interview_platform/application/feedback_services.py`
- [X] T037 [US4] Persist feedback entries/revisions and expose candidate-safe queries in `interview_platform/infrastructure/sqlite_hiring_repository.py`
- [X] T038 [US4] Implement manager feedback and candidate timeline API/UI flows in `interview_platform/web/app.py` and `interview_platform/web/presenters.py`

**Checkpoint**: Two-stage feedback works without leaking rank, fit, signals, notes, or decisions.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [X] T039 Add an idempotent synthetic vacancy-assessment seed and CLI output in `interview_platform/__main__.py`
- [X] T040 [P] Document the runnable vacancy-aware flow and limitations in `README.md`
- [X] T041 Reconcile the implemented routes and schemas with `specs/002-vacancy-fit-assessment/contracts/openapi.yaml`
- [X] T042 Run the full quickstart validation, unit suite, compilation, dry run, and whitespace checks from `specs/002-vacancy-fit-assessment/quickstart.md`

---

## Dependencies & Execution Order

- Phase 1 precedes Phase 2; Phase 2 blocks every story.
- US1 creates approved vacancy context and is the MVP.
- US2 depends on an approved US1 profile and snapshot.
- US3 depends on completed US2 assessment runs.
- US4 depends on US2 assessment evidence but remains independent of US3 ranking and decisions.
- Polish follows all selected stories.

## Parallel Opportunities

- T003 and T008 touch independent configuration/test files.
- Test tasks inside each story can be authored in parallel before their implementation group.
- After US2, US3 and US4 domain/test work can proceed independently because feedback never reads ranking or decisions.
- T040 can proceed independently of final contract reconciliation.

## Parallel Example: User Story 2

```text
Task: "Add context immutability and cross-vacancy isolation tests in tests/test_context_isolation.py"
Task: "Add criterion evidence and aggregation tests in tests/test_assessment.py"
Task: "Add assessment persistence tests in tests/test_assessment_repository.py"
```

## Implementation Strategy

1. Deliver US1 as the smallest browser/API-usable vacancy-memory MVP.
2. Add US2 and validate the core safety claim: the two dimensions do not contaminate each other.
3. Add US3 ranking as a derived, non-decision projection.
4. Add US4 as an append-only candidate communication timeline.
5. Keep legacy interview creation and feedback routes operational until explicit migration is complete.

## Format Validation

All 42 tasks use the required checkbox, sequential task ID, optional `[P]`, required user-story label inside story phases, and concrete file paths.
