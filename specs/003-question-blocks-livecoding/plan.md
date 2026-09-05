# Implementation Plan: Question Blocks, Runtime Clarifications and Live Coding

**Branch**: `003-question-blocks-livecoding` | **Date**: 2026-09-04 | **Spec**: [spec.md](spec.md)

## Summary

Replace the fixed candidate question list with immutable invitation-level question blocks. Persist a
bounded runtime-evaluation job after a completed spoken transcript; the first adapter returns zero
clarifications. Add a plain-text live-coding answer surface and persistence. No code execution,
model call, hiring decision or candidate-visible confidence is included.

## Technical Context

**Language/Version**: Python 3.12; TypeScript 5
**Dependencies**: FastAPI, SQLAlchemy, Alembic, React, Vite
**Storage**: PostgreSQL metadata/text; existing private object storage for continuous media
**Testing**: `unittest`, FastAPI contract tests, Vitest
**Target**: Modern desktop browser and Linux-compatible backend
**Performance**: next base question within three seconds; evaluation never blocks it
**Constraints**: zero to two clarifications only; no code execution; no automatic hiring outcome;
no candidate media/transcripts committed
**Scope**: invitation-scoped blocks, up to 50 base questions and two clarifications per base question

## Constitution Check

- PASS — agent input is limited to question/answer text; no automatic personnel decision.
- PASS — code and transcript remain runtime data, never repository fixtures.
- BLOCKER — current repository has two Alembic heads. Create a merge revision before this feature
  migration so clean-environment upgrades remain reproducible.

## Project Structure

```text
backend/app/interview_config.py       # input validation and block projection
backend/app/models/interview.py       # persistence entities
backend/app/services/                 # candidate workflow and runtime evaluation boundary
backend/app/api/candidate.py          # candidate-safe projections and save APIs
backend/tests/                        # unit and integration coverage
frontend/src/features/interview/      # question renderer and code editor
specs/003-question-blocks-livecoding/ # feature evidence and contracts
```

**Structure Decision**: Extend the existing FastAPI/React candidate flow; no recruiter portal or
agent provider is introduced in this feature.
