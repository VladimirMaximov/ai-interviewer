# Implementation Plan: Asynchronous AI Interview

**Branch**: `001-asynchronous-interview` | **Date**: 2026-09-03 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/001-asynchronous-interview/spec.md`

**Note**: This template is filled in by the `$speckit-plan` command; its definition describes the execution workflow.

## Summary

Build an invitation-only asynchronous interview: consent, animated avatar-led questions, browser
audio responses, resilient uploads, transcription, and evidence-first reviewer access.

## Technical Context

<!--
  ACTION REQUIRED: Replace the content in this section with the technical details
  for the project. The structure here is presented in advisory capacity to guide
  the iteration process.
-->

**Language/Version**: Python 3.12+; TypeScript 5+

**Primary Dependencies**: FastAPI, SQLAlchemy, Alembic, React, Vite, provider adapters

**Storage**: PostgreSQL records; private S3-compatible object storage audio; MinIO locally

**Testing**: Python `unittest`, contract/integration tests, Vitest, browser E2E tests

**Target Platform**: Modern desktop/mobile browsers; Linux containers

**Project Type**: Web application with API and single-page frontend

**Performance Goals**: Next question within 3 seconds; transcript status for 95% of responses within 1 minute

**Constraints**: Private audio; resumable uploads; no automatic rejection or prohibited signals;
provider-portable ASR/TTS; no live WebRTC or streaming video avatar in MVP

**Scale/Scope**: One role, one approved template, six questions, audio-only answers

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- PASS — evidence-first: every AI recommendation cites response/transcript locations.
- PASS — human oversight: AI, recruiter, and hiring-manager decisions are separate; no automatic
  rejection or voice/appearance scoring.
- PASS — privacy: explicit consent, scoped upload grants, private storage, and role checks.
- PASS — deterministic logic: invitation/session transitions and authorization are deterministic.

## Project Structure

### Documentation (this feature)

```text
specs/[###-feature]/
├── plan.md              # This file ($speckit-plan command output)
├── research.md          # Phase 0 output ($speckit-plan command)
├── data-model.md        # Phase 1 output ($speckit-plan command)
├── quickstart.md        # Phase 1 output ($speckit-plan command)
├── contracts/           # Phase 1 output ($speckit-plan command)
└── tasks.md             # Phase 2 output ($speckit-tasks command - NOT created by $speckit-plan)
```

### Source Code (repository root)
<!--
  ACTION REQUIRED: Replace the placeholder tree below with the concrete layout
  for this feature. Delete unused options and expand the chosen structure with
  real paths (e.g., apps/admin, packages/something). The delivered plan must
  not include Option labels.
-->

```text
# [REMOVE IF UNUSED] Option 1: Single project (DEFAULT)
src/
├── models/
├── services/
├── cli/
└── lib/

tests/
├── contract/
├── integration/
└── unit/

# [REMOVE IF UNUSED] Option 2: Web application (when "frontend" + "backend" detected)
backend/
├── src/
│   ├── models/
│   ├── services/
│   └── api/
└── tests/

frontend/
├── src/
│   ├── components/
│   ├── pages/
│   └── services/
└── tests/

# [REMOVE IF UNUSED] Option 3: Mobile + API (when "iOS/Android" detected)
api/
└── [same as backend above]

ios/ or android/
└── [platform-specific structure: feature modules, UI flows, platform tests]
```

**Structure Decision**: [Document the selected structure and reference the real
directories captured above]

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| [e.g., 4th project] | [current need] | [why 3 projects insufficient] |
| [e.g., Repository pattern] | [specific problem] | [why direct DB access insufficient] |
