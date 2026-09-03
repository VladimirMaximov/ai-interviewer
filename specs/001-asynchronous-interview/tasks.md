---
description: "Implementation tasks for the first recording and transcription slice"
---

# Tasks: Asynchronous Interview — Recording and Transcription Slice

**Input**: Design documents from `specs/001-asynchronous-interview/`

**Scope cut**: Deliver recording, durable saving, local and RouterAI transcription, transcript
viewing, and cached Silero question speech. Exclude scoring, evidence extraction, recommendations,
and hiring decisions.

## Phase 1: Setup

- [X] T001 Create FastAPI application package and runtime configuration in `backend/app/main.py` and `backend/app/config.py`
- [ ] T002 Create React/Vite TypeScript application shell in `frontend/package.json` and `frontend/src/main.tsx`
- [ ] T003 [P] Create local PostgreSQL and MinIO development services in `docker-compose.yml`
- [X] T004 [P] Add backend dependency and development commands in `backend/pyproject.toml`
- [ ] T005 [P] Add frontend test commands in `frontend/package.json`

## Phase 2: Foundational Prerequisites

- [ ] T006 Define interview, invitation, session, response, and transcription persistence models in `backend/app/models/interview.py`
- [ ] T007 Add schema migration setup and initial interview tables in `backend/alembic/versions/001_interview_core.py`
- [ ] T008 [P] Define private object-storage interface and MinIO implementation in `backend/app/adapters/storage.py`
- [ ] T009 [P] Define `TranscriptionProvider` and `QuestionSpeechProvider` interfaces in `backend/app/adapters/media.py`
- [X] T010 Implement deterministic invitation/session/response state transitions in `backend/app/domain/interview_state.py`
- [ ] T011 Implement safe API error responses and invitation-token hashing in `backend/app/api/errors.py` and `backend/app/security/invitations.py`
- [X] T012 Add unit tests for state transitions in `backend/tests/unit/test_interview_state.py`; token hashing and invalid-link tests remain in T011

## Phase 3: User Story 1 — Record, Save, and Read Text (Priority: P1) 🎯 MVP

**Goal**: A synthetic invited candidate can consent, hear a question, record an audio answer,
submit it, and see its transcription status and completed text.

**Independent Test**: Start a local session with a synthetic invitation, record one answer in a
browser, confirm it is private and attached to the question, and retrieve its transcript.

- [ ] T013 [P] [US1] Implement local `whisper.cpp` provider invoking multilingual `small` model in `backend/app/adapters/whisper_cpp.py`
- [ ] T014 [P] [US1] Implement RouterAI provider using `openai/gpt-4o-mini-transcribe` and `language="ru"` in `backend/app/adapters/routerai_transcription.py`
- [ ] T015 [P] [US1] Implement local Silero `v5_ru` question-speech provider and asset cache in `backend/app/adapters/silero_tts.py`
- [ ] T016 [US1] Implement response upload confirmation and asynchronous transcription orchestration in `backend/app/services/response_service.py`
- [ ] T017 [US1] Implement candidate invitation, consent, upload-grant, response-confirmation, and transcript-status endpoints in `backend/app/api/candidate.py`
- [ ] T018 [US1] Implement typed candidate API client in `frontend/src/api/candidate.ts`
- [ ] T019 [US1] Implement consent and invitation-state screen in `frontend/src/features/interview/ConsentScreen.tsx`
- [ ] T020 [US1] Implement question player with cached speech and text alternative in `frontend/src/features/interview/QuestionPlayer.tsx`
- [ ] T021 [US1] Implement MediaRecorder start/stop, unsent-answer replacement, and upload retry in `frontend/src/features/interview/AudioRecorder.tsx`
- [ ] T022 [US1] Assemble candidate interview flow and transcript-status view in `frontend/src/features/interview/InterviewPage.tsx`
- [ ] T023 [P] [US1] Add backend contract and integration tests for consent, upload confirmation, and transcript states in `backend/tests/integration/test_candidate_recording.py`
- [ ] T024 [P] [US1] Add frontend tests for microphone denial, recording state, and transcript status in `frontend/src/features/interview/InterviewPage.test.tsx`
- [ ] T025 [US1] Add browser E2E synthetic-audio happy-path test in `frontend/tests/e2e/candidate-recording.spec.ts`

## Phase 4: User Story 2 — Resume after Interruption (Priority: P2)

**Goal**: The candidate can return through the same valid invitation and continue without losing a
confirmed response.

**Independent Test**: Confirm one audio answer, reload the browser, and verify it remains saved and
the next unfinished question is restored.

- [ ] T026 [US2] Implement session-resume endpoint and current-question calculation in `backend/app/api/candidate.py`
- [ ] T027 [US2] Implement browser resume and progress restoration in `frontend/src/features/interview/useInterviewSession.ts`
- [ ] T028 [P] [US2] Add backend interruption/retry regression tests in `backend/tests/integration/test_session_resume.py`
- [ ] T029 [P] [US2] Add browser reload/retry E2E test in `frontend/tests/e2e/session-resume.spec.ts`

## Phase 5: Polish and Validation

- [ ] T030 [P] Add synthetic Russian technical-audio fixtures and expected transcripts in `backend/tests/fixtures/transcription/`
- [ ] T031 Compare `whisper.cpp small`, `whisper.cpp large-v3-turbo`, and RouterAI on the fixtures; record accuracy and latency without candidate data in `research/transcription-benchmark.md`
- [ ] T032 Add adapter configuration, key-handling, and local model-install instructions in `backend/README.md`
- [ ] T033 Run `python -m unittest discover -s tests -v` and `python -m compileall -q product_engineering`; record results in `specs/001-asynchronous-interview/quickstart.md`

## Dependencies & Execution Order

- T001–T005 → T006–T012 → US1 (T013–T025) → US2 (T026–T029) → T030–T033.
- T013, T014, and T015 can proceed in parallel after adapter interfaces exist.
- T018–T021 can proceed in parallel after the candidate contract is stable.

## MVP Strategy

Implement through T025 first. It proves the entire candidate value loop with local Whisper and
Silero; RouterAI is an optional comparison adapter, not a blocker. Do not implement score,
recommendation, or reviewer-decision tasks in this slice.
