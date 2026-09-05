# Implementation Plan: Integrated Interview Runtime

**Branch**: `main` | **Date**: 2026-09-05 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/004-integrated-interview-runtime/spec.md`

## Summary

Keep the Vite candidate interview and CRA internal cabinet as separate frontends, but make the existing FastAPI/PostgreSQL backend authoritative for both. Replace the cabinet's SQLite/demo API and mocks with typed endpoints over the existing vacancy, invitation, session, response, code, transcript, follow-up, and assessment models. Extract Napoleon IT visual tokens into a small shared package consumed by both frontends. Add durable asynchronous media jobs: XTTS v2 produces multilingual question audio, then MuseTalk renders an MP4 from the approved portrait and that exact audio. Known questions are warmed after invitation creation; runtime follow-ups use the same queue and fall back to audio plus a static portrait.

## Technical Context

**Language/Version**: Python 3.12+, TypeScript (existing Vite and CRA toolchains)

**Primary Dependencies**: FastAPI, Pydantic, SQLAlchemy, Alembic, React, XTTS v2, MuseTalk, ffmpeg, CUDA-enabled PyTorch, Redis, Celery

**Storage**: PostgreSQL for authoritative metadata and job state; MinIO/S3 for recordings and generated media; Redis only as the task broker

**Testing**: `unittest` backend suite, Vitest candidate UI, React Testing Library/Jest cabinet UI, contract tests, synthetic E2E smoke test

**Target Platform**: Ubuntu 24.04 server, NVIDIA Tesla T4 16 GB VRAM, 32 GB RAM; current desktop Safari/Chrome candidate targets

**Project Type**: Two web frontends, one API service, and background CPU/GPU workers

**Performance Goals**: warmed media within 2 seconds at p95; new follow-up presenter asset within 15 seconds in 90% of single-interview demo runs; ten-second recording chunks remain continuous

**Constraints**: one guaranteed simultaneous interview; one serialized GPU presenter queue; candidate flow never blocked by avatar failure; no password authentication; no candidate PII or media committed to Git

**Scale/Scope**: hackathon prototype, one server, three fixed block categories, variable question counts, spoken and coding questions

## Constitution Check

The constitution file is an unfilled template, so repository `AGENTS.md` is the enforceable gate:

- PASS: Python 3.12+, type hints, and small single-purpose modules.
- PASS: one authoritative schema and deterministic limits.
- PASS: evidence classifications and assessment links remain explicit.
- PASS: no automatic rejection or scoring of appearance, accent, emotion, or voice confidence.
- PASS: all fixtures and E2E data are synthetic; no recordings, transcripts, secrets, or candidate PII enter Git.
- PASS: parsing, schemas, retries, resume behavior, and integration changes receive regression tests.

Post-design check: PASS. The contract uses opaque invitation tokens, explicit processing states, evidence references, and non-blocking degradation. Password authentication is excluded rather than implemented insecurely.

## Project Structure

### Documentation (this feature)

```text
specs/004-integrated-interview-runtime/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/openapi.yaml
└── tasks.md
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── api/                 # cabinet, candidate, and presenter endpoints
│   ├── adapters/            # XTTS, MuseTalk, S3, STT
│   ├── models/              # authoritative PostgreSQL models
│   ├── services/            # configuration, results, jobs, orchestration
│   └── workers/             # durable CPU/GPU task entrypoints
├── alembic/versions/
└── tests/{unit,integration}/

frontend/                    # candidate experience (Vite)
frontend_ux/                 # recruiter/manager cabinet (CRA)
packages/brand-tokens/       # shared visual tokens
deploy/                      # compose and reverse-proxy configuration
```

**Structure Decision**: Preserve the two existing frontend applications because their users and layouts differ. Retire `backend_ux` as a runtime service after the cabinet is migrated; do not create a second production database or duplicate domain models.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Two frontend builds | Candidate recording and internal review have materially different runtime and UX needs | Combining them now risks regressions in the already working media flow |
| Redis plus workers | GPU generation and transcription must survive API request boundaries and be serialized | In-process threads lose jobs on restart and can exhaust GPU memory |
