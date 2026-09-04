# Tasks: Session-scoped Multi-agent Candidate Matching

**Input**: Design documents from `/specs/003-multi-agent-interview-flow/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md`

**Tests**: Regression tests are required by repository guidelines and are written before each story's
implementation.

**Organization**: Tasks are grouped by independently verifiable user story.

## Phase 1: Setup (Shared Contracts)

- [x] T001 Define strict multi-agent enums, payload models, public views, errors, and provider protocols in `backend/app/domain/multi_agent.py`
- [x] T002 Add versioned strong-pool thresholds and multi-agent provider configuration in `backend/app/config.py`
- [x] T003 [P] Replace feature contracts and validation guide in `specs/003-multi-agent-interview-flow/contracts/` and `specs/003-multi-agent-interview-flow/quickstart.md`

---

## Phase 2: Foundational (Blocking Prerequisites)

- [x] T004 [P] Add migration regression tests for session, operation, run, artifact, ranking, and restriction tables in `backend/tests/integration/test_multi_agent_migration.py`
- [x] T005 Add additive SQLAlchemy persistence models and constraints in `backend/app/models/multi_agent.py`
- [x] T006 Add Alembic migration `005_multi_agent_harness.py` in `backend/alembic/versions/005_multi_agent_harness.py`
- [x] T007 Register the multi-agent models in Alembic metadata in `backend/alembic/env.py`
- [x] T008 Add canonical hashing, operation idempotency, attempt audit, output validation, and artifact materialization foundation in `backend/app/services/multi_agent_harness.py`
- [x] T009 Add provider-independent deterministic aggregation and compatibility helpers in `backend/app/services/multi_agent_harness.py`

**Checkpoint**: Generic agent stages can fail, retry, validate, persist, and resume without creating an
artifact from invalid output.

---

## Phase 3: User Story 1 - Isolated harness session (Priority: P1) 🎯 MVP

**Goal**: Pin one candidate/vacancy context and expose an idempotent recruiter-owned session.

**Independent Test**: Two applications create distinct immutable inputs; same-key replay returns the
same session and cross-vacancy access fails.

### Tests for User Story 1

- [x] T010 [P] [US1] Add session pinning, optional brief, idempotency, and cross-context isolation tests in `backend/tests/unit/test_multi_agent_harness.py`
- [x] T011 [P] [US1] Add create/get session HTTP contract tests in `backend/tests/integration/test_multi_agent_api.py`

### Implementation for User Story 1

- [x] T012 [US1] Implement session creation, pinned manager/resume selection, and recruiter projection in `backend/app/services/multi_agent_harness.py`
- [x] T013 [US1] Add recruiter session endpoints, dependency provider, and exception mapping in `backend/app/api/multi_agent.py`
- [x] T014 [US1] Register harness factory and router in `backend/app/database.py` and `backend/app/main.py`

**Checkpoint**: The session is reproducible, isolated, and runnable without manager wishes or a resume.

---

## Phase 4: User Story 2 - Resume relevance and question plan (Priority: P2)

**Goal**: Match source-backed resume experience to the primary vacancy and create stable baseline plus
bounded claim-verification questions.

**Independent Test**: A three-position synthetic resume produces exact excerpts, requirement links,
gaps, a stable baseline, and sourced personalized questions.

### Tests for User Story 2

- [x] T015 [P] [US2] Add source provenance, no-resume, relevance, baseline stability, and bounded personalization tests in `backend/tests/unit/test_multi_agent_harness.py`
- [x] T016 [P] [US2] Add resume-analysis and question-plan endpoint tests in `backend/tests/integration/test_multi_agent_api.py`

### Implementation for User Story 2

- [x] T017 [US2] Implement OpenAI Responses resume-relevance and question-planning agents with strict Structured Outputs in `backend/app/adapters/openai_interview_agents.py`
- [x] T018 [US2] Implement purpose-specific resume and planning manifests plus artifact validation in `backend/app/services/multi_agent_harness.py`
- [x] T019 [US2] Add idempotent resume-analysis, recruiter question-plan, and candidate-safe question endpoints in `backend/app/api/multi_agent.py` and `frontend/src/api/candidate.ts`

**Checkpoint**: Resume text remains claim context, and all personalized questions trace to pinned claims.

---

## Phase 5: User Story 3 - Per-answer evidence scoring (Priority: P3)

**Goal**: Assess only stored completed transcripts using independent dimensions and exact evidence.

**Independent Test**: A technically negative answer changes only technical evidence; a missing signal
is null; fabricated excerpts and arbitrary values are rejected without losing the answer.

### Tests for User Story 3

- [x] T020 [P] [US3] Add exact scale, evidence span, dimension isolation, save-before-evaluate, invalid-output, and retry tests in `backend/tests/unit/test_multi_agent_harness.py`
- [x] T021 [P] [US3] Add stored-response assessment HTTP tests in `backend/tests/integration/test_multi_agent_api.py`

### Implementation for User Story 3

- [x] T022 [US3] Implement the OpenAI Responses answer-assessment agent with strict Structured Outputs in `backend/app/adapters/openai_interview_agents.py`
- [x] T023 [US3] Implement question lookup, completed-transcript guard, evidence validation, and assessment orchestration in `backend/app/services/multi_agent_harness.py`
- [x] T024 [US3] Add the answer-assessment endpoint in `backend/app/api/multi_agent.py`

**Checkpoint**: Every numeric observation is grounded in the stored answer and no dimension borrows
another dimension's evidence.

---

## Phase 6: User Story 4 - Candidate profile and primary ranking (Priority: P4)

**Goal**: Build a deterministic profile and stable compatible vacancy ranking without a hiring action.

**Independent Test**: Three compatible profiles rank identically on replay; null evidence affects
coverage, not score; an incompatible profile is excluded.

### Tests for User Story 4

- [x] T025 [P] [US4] Add criterion/dimension aggregation, coverage, compatibility, tie-break, and no-decision tests in `backend/tests/unit/test_multi_agent_harness.py`
- [x] T026 [P] [US4] Add finalize and ranking endpoint tests in `backend/tests/integration/test_multi_agent_api.py`

### Implementation for User Story 4

- [x] T027 [US4] Implement immutable candidate profile materialization and strong-pool eligibility in `backend/app/services/multi_agent_harness.py`
- [x] T028 [US4] Implement compatible vacancy ranking snapshots and projections in `backend/app/services/multi_agent_harness.py`
- [x] T029 [US4] Add finalize and vacancy-ranking endpoints in `backend/app/api/multi_agent.py`

**Checkpoint**: Ranking is reproducible and never modifies invitation or hiring state.

---

## Phase 7: User Story 5 - Alternative vacancy matching (Priority: P5)

**Goal**: Recommend explainable active alternatives only for eligible evidence-backed profiles.

**Independent Test**: A strong mismatched candidate receives a relevant alternative while low-score,
low-coverage, incompatible, and restricted profiles receive no published recommendation.

### Tests for User Story 5

- [x] T030 [P] [US5] Add active-catalog, matched-term, grade compatibility, eligibility, and restriction tests in `backend/tests/unit/test_multi_agent_harness.py`
- [x] T031 [P] [US5] Extend finalization HTTP tests with alternative match projections in `backend/tests/integration/test_multi_agent_api.py`

### Implementation for User Story 5

- [x] T032 [US5] Implement the OpenAI Responses alternative-vacancy agent with strict Structured Outputs in `backend/app/adapters/openai_interview_agents.py`
- [x] T033 [US5] Implement catalog context, eligibility gate, alternative artifact validation, and ordering in `backend/app/services/multi_agent_harness.py`
- [x] T034 [US5] Include safe alternative matches in finalization and session projections in `backend/app/api/multi_agent.py`

**Checkpoint**: No ineligible profile appears in the strong-candidate pool or creates a new application.

---

## Phase 8: User Story 6 - Integrity review and human restrictions (Priority: P6)

**Goal**: Surface source-backed contradictions without automatic blacklisting and maintain append-only
human decisions.

**Independent Test**: A contradiction produces only a review observation; an authenticated human can
append, supersede, expire, and clear a restriction while scores and agent artifacts remain unchanged.

### Tests for User Story 6

- [x] T035 [P] [US6] Add contradiction, no-auto-blacklist, human authority, supersession, expiry, and clear tests in `backend/tests/unit/test_multi_agent_harness.py`
- [x] T036 [P] [US6] Add restriction history and authorization contract tests in `backend/tests/integration/test_multi_agent_api.py`

### Implementation for User Story 6

- [x] T037 [US6] Implement the OpenAI Responses integrity-check agent without restriction vocabulary in `backend/app/adapters/openai_interview_agents.py`
- [x] T038 [US6] Implement integrity orchestration and append-only effective restriction rules in `backend/app/services/multi_agent_harness.py`
- [x] T039 [US6] Add human restriction create/list endpoints in `backend/app/api/multi_agent.py`

**Checkpoint**: Only the authenticated actor can create restriction decisions; agent outputs remain
observations and preserve all evidence.

---

## Phase 9: Polish & Cross-Cutting Concerns

- [x] T040 [P] Document harness configuration, API journey, scoring semantics, alternatives, and human-only restrictions in `backend/README.md`
- [x] T041 [P] Add multi-agent model imports and architecture regression coverage where required in `backend/app/models/__init__.py` and `tests/test_interview_architecture.py`
- [x] T042 Reconcile implemented routes and payloads with `specs/003-multi-agent-interview-flow/contracts/openapi.yaml`
- [x] T043 Run root tests, backend tests, compileall, and JSON/YAML contract parsing; fix all regressions in touched files
- [x] T044 [P] Load server-generated question IDs in `frontend/src/features/interview/InterviewPage.tsx` and cover the candidate API in `frontend/src/api/candidate.test.ts`
- [x] T045 Run frontend tests and the production TypeScript/Vite build; fix all regressions in touched files
- [x] T046 [P] Add a 1,000-profile isolation and sub-two-second ranking regression in `backend/tests/unit/test_multi_agent_scale.py`

## Dependencies & Execution Order

- Phase 1 precedes the persistence foundation in Phase 2.
- US1 depends on the foundation and creates the pinned context for every later story.
- US2 depends on US1 and produces the question plan used by US3.
- US3 depends on US2 and produces observations used by US4.
- US4 creates the evidence profile and ranking used by US5.
- US5 depends on the profile eligibility result but is independent of integrity analysis when no flag
  or restriction exists.
- US6 uses the same profile/session inputs and can be disabled without changing previous artifacts.
- Phase 9 validates all selected stories.

## Parallel Opportunities

- Migration, unit, and HTTP test files are independent until their corresponding implementation.
- Domain contracts and configuration can be prepared independently.
- Within each story, unit and HTTP tests touch separate files.
- Documentation and architecture checks can run after the public contract stabilizes.

## Implementation Strategy

1. Complete T001–T014 for a runnable isolated harness MVP.
2. Add resume relevance and question planning with T015–T019.
3. Add answer scoring and deterministic profile/ranking with T020–T029.
4. Add alternative matching and integrity/human restriction flow with T030–T039.
5. Finish docs, candidate UI wiring, scale coverage, and all quality gates with T040–T046.

All 46 tasks use the required checklist format, sequential task IDs, story labels inside story phases,
and concrete repository paths.
