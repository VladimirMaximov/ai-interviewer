# Tasks: Question Blocks, Runtime Clarifications and Live Coding

## Dependencies

`US1` → `US2` and `US3`. The Alembic merge is required before any new feature migration.

## Phase 1 — Foundation

- [X] T001 Add an Alembic merge revision for `003_vacancy_resume_context` and `008_invitation_question_input` in `backend/alembic/versions/`
- [X] T002 Add block/question input models, validation and candidate-safe projection in `backend/app/interview_config.py`
- [X] T003 Add regression tests for ordered blocks, duplicate IDs and hidden policy flags in `backend/tests/unit/test_interview_config.py`

## Phase 2 — Question blocks (US1)

- [X] T004 [US1] Persist invitation block snapshots and migrate existing input in `backend/app/models/interview.py` and `backend/alembic/versions/`
- [X] T005 [US1] Return ordered block questions from `backend/app/services/candidate_workflow.py` and `backend/app/api/candidate.py`
- [X] T006 [US1] Render configured question type and hide prompts before recording starts in `frontend/src/features/interview/InterviewPage.tsx`
- [X] T007 [US1] Add candidate API contract coverage for ordered blocks in `backend/tests/integration/test_candidate_recording.py`

## Phase 3 — Runtime clarification boundary (US2)

- [X] T008 [US2] Add runtime evaluation job model, migration and state enum in `backend/app/models/interview.py` and `backend/alembic/versions/`
- [X] T009 [US2] Define strict request/decision schemas and zero-question stub adapter in `backend/app/services/runtime_evaluation.py`
- [X] T010 [US2] Trigger one non-blocking evaluation only after eligible transcript completion in `backend/app/services/transcription_scheduler.py`
- [X] T011 [US2] Validate and persist zero-to-two clarification prompts per base response in `backend/app/services/candidate_workflow.py`
- [X] T012 [US2] Add stub, malformed decision, two-prompt cap and no-blocking regression tests in `backend/tests/unit/test_runtime_evaluation.py`

## Phase 4 — Live coding (US3)

- [X] T013 [US3] Add `CodeAnswer` persistence with language and continuous-recording start/end offsets plus save endpoint in `backend/app/models/interview.py`, `backend/app/api/candidate.py` and a migration
- [X] T014 [US3] Add code-editor component with language picker and draft state in `frontend/src/features/interview/CodeEditor.tsx`
- [X] T015 [US3] Keep camera/microphone recording active and save code with the coding-question boundary in `frontend/src/features/interview/InterviewPage.tsx`
- [X] T016 [US3] Add persistence and no-execution tests in `backend/tests/integration/test_candidate_recording.py`

## Phase 5 — Validation and documentation

- [X] T017 Update the input example and quickstart in `specs/003-question-blocks-livecoding/`
- [X] T018 Run backend, frontend and migration validation commands and record results in `specs/003-question-blocks-livecoding/quickstart.md`
