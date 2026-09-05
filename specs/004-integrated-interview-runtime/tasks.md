# Tasks: Integrated Interview Runtime

**Input**: Design documents from `specs/004-integrated-interview-runtime/`

**Tests**: Regression, contract, retry/idempotency, and synthetic E2E tests are required by FR-018.

## Phase 1: Setup

- [X] T001 Add Redis, API, CPU worker, GPU presenter worker, and both frontend service skeletons to `deploy/docker-compose.prototype.yml`
- [X] T002 [P] Add pinned queue dependencies to `backend/pyproject.toml` and the isolated XTTS, MuseTalk, CUDA stack to `deploy/images/presenter-requirements.txt`
- [X] T003 [P] Add non-secret API, queue, presenter, public URL, and timeout settings to `.env.example` and `backend/app/config.py`
- [X] T004 [P] Add generated media, local model, SQLite, transcript, recording, and secret exclusions to `.gitignore` and `.dockerignore`

## Phase 2: Foundational

- [X] T005 Add normalized question snapshot and presenter/job tables in `backend/alembic/versions/017_integrated_runtime.py`
- [X] T006 [P] Add typed configuration and presenter state models in `backend/app/domain/interview_runtime.py`
- [X] T007 [P] Add SQLAlchemy presenter asset and durable processing job models in `backend/app/models/interview.py`
- [X] T008 Implement configuration normalization, validation, content hashing, and snapshot compatibility in `backend/app/interview_config.py`
- [X] T009 Implement Celery routing with separate CPU and serialized GPU queues in `backend/app/workers/celery_app.py`
- [X] T010 Implement idempotent job creation, retry transitions, and stale-running recovery in `backend/app/services/job_queue.py`
- [X] T011 [P] Add schema, malformed-input, idempotency, and job-transition tests in `backend/tests/unit/test_integrated_runtime.py`
- [X] T012 [P] Create reusable Napoleon IT CSS variables and primitives in `packages/brand-tokens/src/tokens.css`

## Phase 3: User Story 1 - Configure and launch an interview (P1) 🎯 MVP

**Goal**: Cabinet-created configuration produces a real candidate invitation and completed session in the main database.

**Independent Test**: Create a synthetic three-block configuration and invitation through the cabinet, open the returned URL, and verify that the completed session is linked to the same vacancy and snapshot.

- [X] T013 [P] [US1] Add contract tests for configuration and invitation endpoints in `backend/tests/integration/test_recruiter_interview_configuration.py`
- [X] T014 [P] [US1] Add cabinet API mapping tests in `frontend_ux/src/api.test.ts`
- [X] T015 [US1] Implement editable configuration and immutable invitation snapshot services in `backend/app/services/interview_configuration.py`
- [X] T016 [US1] Add configuration and invitation endpoints from the feature contract to `backend/app/api/hiring_context.py`
- [X] T017 [US1] Register the unified recruiter routes and factories in `backend/app/main.py` and `backend/app/database.py`
- [X] T018 [US1] Replace `backend_ux` vacancy calls with typed main-backend calls in `frontend_ux/src/api.ts` and `frontend_ux/src/types.ts`
- [X] T019 [US1] Replace the flat question form with three blocks, kind, timer, coding language, and follow-up controls in `frontend_ux/src/pages/Vacancy.tsx`
- [X] T020 [US1] Add real invitation creation, one-time URL display, and copy action in `frontend_ux/src/pages/Homepage.tsx`
- [X] T021 [US1] Remove password/login dependency from cabinet routing and use configured demo actor identity in `frontend_ux/src/App.tsx` and `frontend_ux/src/api.ts`
- [X] T022 [US1] Add a synthetic cabinet-to-candidate integration test in `backend/tests/integration/test_integrated_interview_e2e.py`

## Phase 4: User Story 2 - Visually consistent candidate experience (P2)

**Goal**: Both applications share the cabinet's visual language without changing the working media behavior.

**Independent Test**: Complete spoken and coding questions after one permission flow while both applications use the same tokens and candidate-specific layouts remain intact.

- [X] T023 [P] [US2] Add regression tests for hidden first question, single permission flow, and completion copy in `frontend/src/features/interview/InterviewPage.test.tsx`
- [X] T024 [P] [US2] Import shared tokens and map cabinet Bootstrap variables in `frontend_ux/src/styles.css`
- [X] T025 [US2] Import shared tokens and restyle preparation, interview, coding, debug, and completion states in `frontend/src/styles.css`
- [X] T026 [US2] Refine candidate layout components without altering stream ownership in `frontend/src/features/interview/ConsentScreen.tsx` and `frontend/src/features/interview/InterviewPage.tsx`
- [X] T027 [US2] Verify continuous recording, ten-second chunks, boundaries, coding timeout, and media cleanup in `frontend/src/features/interview/AudioRecorder.test.tsx`

## Phase 5: User Story 3 - Runtime multilingual presenter (P2)

**Goal**: XTTS creates multilingual audio and MuseTalk creates lip-synced question video on the Tesla T4, with warm-cache and static fallback paths.

**Independent Test**: Generate and play a configured mixed-language prompt and a newly created follow-up; force avatar failure and confirm that audio plus static portrait continues the interview.

- [X] T028 [P] [US3] Add XTTS request, output validation, and mixed-language tests in `backend/tests/unit/test_xtts_runtime.py`
- [X] T029 [P] [US3] Add MuseTalk command, even-dimension, timeout, and failure tests in `backend/tests/unit/test_musetalk_runtime.py`
- [X] T030 [US3] Convert the existing XTTS script into a persistent worker adapter in `backend/app/adapters/xtts_runtime.py`
- [X] T031 [US3] Implement MuseTalk rendering with ffmpeg validation and bounded diagnostics in `backend/app/adapters/musetalk_runtime.py`
- [X] T032 [US3] Implement audio-first presenter orchestration and S3 persistence in `backend/app/services/presenter_assets.py`
- [X] T033 [US3] Add prewarm and on-demand GPU tasks with concurrency-one routing in `backend/app/workers/presenter_tasks.py`
- [X] T034 [US3] Queue configured assets after invitation creation and follow-up assets after runtime evaluation in `backend/app/services/hiring_context.py` and `backend/app/services/runtime_evaluation.py`
- [X] T035 [US3] Add token-scoped presenter status and signed-media endpoints in `backend/app/api/candidate.py`
- [X] T036 [P] [US3] Add presenter API polling and state types in `frontend/src/api/candidate.ts` and `frontend/src/api/candidate.test.ts`
- [X] T037 [US3] Replace keyframe-only playback with generated video, exact-once audio, bounded polling, and static fallback in `frontend/src/features/interview/InterviewerAvatar.tsx` and `frontend/src/features/interview/useQuestionSpeech.ts`
- [X] T038 [US3] Add integration tests for prewarm deduplication, dynamic follow-up generation, retries, and fallback in `backend/tests/integration/test_presenter_runtime.py`

## Phase 6: User Story 4 - Review real results (P3)

**Goal**: The cabinet lists and opens actual sessions, recordings, transcripts, code, follow-ups, and evidence-linked assessments.

**Independent Test**: Complete a synthetic interview and verify every cabinet field against its persisted backend record without mock fallbacks.

- [X] T039 [P] [US4] Add result-list/detail contract tests including pending and failed artifacts in `backend/tests/integration/test_recruiter_results.py`
- [X] T040 [US4] Implement vacancy interview summary and session detail projections in `backend/app/services/interview_results.py`
- [X] T041 [US4] Add recruiter result endpoints with signed media URLs in `backend/app/api/hiring_context.py`
- [X] T042 [P] [US4] Add result response types and mapping tests in `frontend_ux/src/types.ts` and `frontend_ux/src/api.test.ts`
- [X] T043 [US4] Remove `MOCK_CANDIDATES` fallback and render explicit lifecycle states in `frontend_ux/src/pages/Leaderboard.tsx`
- [X] T044 [US4] Replace mock transcript/video with question-aligned real artifacts and evidence links in `frontend_ux/src/pages/CandidateDetails.tsx`
- [X] T045 [US4] Add cabinet component tests for empty, pending, failed, spoken, coding, and follow-up results in `frontend_ux/src/pages/CandidateDetails.test.tsx`

## Phase 7: Polish and local release gate

- [X] T046 [P] Document model acquisition, pinned versions, and local cache paths in `docs/runtime-presenter.md`
- [X] T047 Add health/readiness checks for database, object storage, Redis, CUDA, XTTS, and MuseTalk in `backend/app/api/health.py`
- [X] T048 Add Nginx routing for cabinet `/`, candidate `/interview`, API `/api`, and private media redirects in `deploy/nginx/default.conf`
- [X] T049 Add resource limits, persistent volumes, restart policy, model mounts, and GPU reservation to `deploy/docker-compose.prototype.yml`
- [ ] T050 Run every command and E2E/failure scenario in `specs/004-integrated-interview-runtime/quickstart.md` and record results in `deliverables/ai-technical-interview/integrated-runtime-validation.md`
- [X] T051 Audit `git status` and tracked objects to ensure no secrets, candidate PII, databases, recordings, transcripts, or generated avatar media are included

## Dependencies and execution order

- Phase 1 precedes Phase 2; Phase 2 blocks all user stories.
- US1 is the MVP and should be completed first because it establishes the authoritative data path.
- US2 may follow US1 independently of GPU work.
- US3 depends on invitation snapshots and the durable job foundation, not on the US2 redesign.
- US4 depends on US1 persistence; it can proceed alongside US3.
- Deployment polish begins only after desired user stories pass their independent tests.

## Parallel opportunities

- T002–T004 and T011–T012 touch independent files.
- Within US1, backend contract tests and cabinet API tests can be prepared together.
- US2 token mapping and candidate regression tests can proceed together.
- US3 XTTS and MuseTalk adapters/tests can be built independently before orchestration.
- US4 backend projections and frontend response types can be prepared in parallel after the contract is fixed.

## Implementation strategy

1. **MVP A**: T001–T022 — a cabinet-created link drives a real candidate interview.
2. **MVP B**: T023–T027 — both UIs look like one product without media regressions.
3. **Demo differentiator**: T028–T038 — runtime multilingual voice and lip-synced avatar on T4.
4. **Closed loop**: T039–T045 — real interview results replace cabinet mocks.
5. **Server candidate**: T046–T051 — only after local E2E and failure testing pass.

All 51 tasks follow the required checkbox, sequential ID, story label, and file-path format.
