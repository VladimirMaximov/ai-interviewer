# Implementation Plan: Unified Interview Demonstration Cabinet

**Branch**: `005-unified-interview-cabinet` | **Date**: 2026-09-06 | **Spec**: `specs/005-unified-interview-cabinet/spec.md`

## Summary

Keep a single recruiter cabinet as the application entry point. Candidates enter only through recruiter-generated links. Extend the existing FastAPI/PostgreSQL/MinIO interview runtime so invitations, imported material profiles, candidate-entered resume text, recording metadata, question intervals, agent assessments, reports, and review-only antifraud events persist under separate invitation/session identities. Add a read-only recruiter vacancy view, leaderboard, candidate detail page, HTTP range video delivery, durable assessment orchestration, and an import path for all 11 supplied Python candidate profiles; synthetic fixtures remain a separate fallback/demo dataset, not a replacement for those responses.

## Technical Context

**Language/Version**: Python 3.12+; TypeScript/React for the Vite candidate UI and recruiter UI.

**Primary Dependencies**: FastAPI, Pydantic, SQLAlchemy/Alembic, PostgreSQL, Redis/Celery-compatible durable jobs, MinIO/S3-compatible storage, existing agent services; React, Vite, MediaRecorder, existing frontend test tooling.

**Storage**: PostgreSQL for identities, vacancy configuration, lifecycle, transcripts, assessments, reports, and timestamps; private MinIO/S3 for recordings and synthetic media; Redis/job queue for retryable transcription and assessment work.

**Testing**: Existing Python `unittest` unit/integration suites, frontend tests in the respective package, API contract tests, and remote smoke/E2E checks. Run `python -m unittest discover -s backend/tests -v` and `python -m compileall -q backend/app` from the repository root where applicable.

**Target Platform**: Docker Compose deployment on the remote Ubuntu server at `/opt/ai-interviewer`, served through the existing HTTPS gateway; current Chrome/Safari desktop candidate and recruiter flows.

**Project Type**: Web application with FastAPI backend, candidate web client, recruiter UX client, background processing, and S3-compatible media storage.

**Performance Goals**: Support at least two concurrent candidate sessions without cross-session data; return a recruiter leaderboard promptly for ten synthetic rows; serve range requests and seek to a stored question offset within one second after media is available.

**Constraints**: Keep media private and stream by byte range; do not commit recordings, transcripts, candidate PII, or secrets; use opaque non-guessable invitation tokens; preserve evidence-first assessment and human review; never score appearance, accent, emotion, or voice confidence; manager and standalone candidate cabinets remain deferred.

**Scale/Scope**: One confirmed vacancy (`Middle+ Python Developer`), 11 supplied candidate profiles to import before agent evaluation, optional synthetic fixtures for demo gaps, several future real team interviews, multiple simultaneous invitations, and one recruiter read-only results workflow. A second vacancy is not invented from the supplied materials.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Evidence-first evaluation**: PASS. Question assessments retain evidence, criterion-level values, confidence, and missing evidence; recruiter and future human decisions remain separate.
- **Deterministic scoring**: PASS. Aggregation and ranking are implemented in backend code, not delegated to an LLM.
- **Privacy and synthetic data**: PASS. Real media requires consent and access control; fixtures are explicitly synthetic and are not stored as candidate PII.
- **Fairness boundary**: PASS. Antifraud is reviewer-only and prohibited attributes are not scoring inputs.
- **Validation discipline**: PASS. Schema, migration, lifecycle, range delivery, concurrency, and UI flows receive regression coverage before remote rollout.

The repository constitution file is still the starter template, so these gates are derived from the supplied repository `AGENTS.md` and existing domain rules. No gate is violated.

## Project Structure

### Documentation (this feature)

```text
specs/005-unified-interview-cabinet/
├── spec.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/openapi.yaml
├── checklists/requirements.md
└── plan.md
```

### Source Code (repository root)

```text
backend/
├── app/api/                 # recruiter, candidate, media, and agent routes
├── app/domain/              # lifecycle, assessment, proctoring, and schemas
├── app/models/              # SQLAlchemy persistence models
├── app/services/            # workflow, results, media, and orchestration services
├── app/workers/             # transcription and durable assessment jobs
├── alembic/versions/        # additive schema migrations
└── tests/{unit,integration}/
frontend/src/                # candidate invitation and preflight flow
frontend_ux/src/             # recruiter entry, vacancies, leaderboard, detail
deploy/                      # Docker Compose, gateway, and remote deployment scripts
```

## Implementation Phases

### Phase 1 — Persistence and contracts

1. Map existing vacancy, invitation, session, response, result, monitoring, and hiring-context models to the feature entities.
2. Add additive migrations for manager brief/version, candidate alias and resume text, invitation/session source and lifecycle fields, media object metadata, question intervals, report/assessment readiness, and synthetic fixture markers.
3. Enforce opaque token lookup, invitation ownership, immutable source kind, valid status transitions, bounded text sizes, and unique question intervals per session.
4. Add recruiter and candidate API schemas plus protected media range contract.

### Phase 2 — Unified entry and recruiter workflow

1. Add the three-choice entry screen while keeping manager and standalone candidate behavior explicitly deferred.
2. Replace vacancy “Вопросы” with read-only “Редактировать”; show description, requirements, and manager brief without mutation in the demo.
3. Add “Результаты” navigation, leaderboard filters/statuses, and candidate detail route.
4. Ensure all recruiter detail endpoints are view-only and cannot expose another vacancy or invitation.

### Phase 3 — Candidate link and lifecycle

1. Add pre-interview form for display name and text resume, validating and persisting both before consent/start.
2. Keep each link/session isolated and resumable; return clear invalid, expired, completed, and in-progress states.
3. Persist question start/end offsets, response status, transcription status, recording state, and completion timestamps.
4. Connect candidate completion to durable answer assessment, follow-up generation, integrity check, final aggregation, and report generation with retry/idempotency keys.

### Phase 4 — Media and evidence presentation

1. Store recordings outside the database with content type, byte size, duration, checksum, and private object key.
2. Implement authorized `206 Partial Content`/`416` range handling and seekable playback; never proxy an unbounded public object.
3. Render question timestamps, assessment labels/values, evidence links, summary, full report, and reviewer-only antifraud intervals.
4. Render missing media/timestamp/assessment states explicitly instead of fabricating evidence.

### Phase 5 — Demonstration data and remote rollout

1. Import the 11 supplied Python profiles as persisted отклики linked to the confirmed vacancy, preserving source filename and profile text; do not run agent evaluation in this data-loading phase.
2. Seed synthetic candidates only where needed for a complete demo, marking every fixture and derived result as synthetic in API and UI.
3. Add regression and E2E coverage for parallel links, completion transitions, assessment retries, authorization, range requests, timestamp seeking, and profile import.
4. On the remote server, run migration, build/restart services, import profiles idempotently, then smoke-test HTTPS, candidate link, leaderboard, detail, and media range delivery.

## Design Notes

- Existing agent stages remain the source of assessment semantics. New orchestration calls them from trusted backend jobs rather than from the candidate browser.
- `CriterionDefinition.weight` is preserved in the model, but current profile aggregation is an arithmetic mean; any weighted ranking change requires a separate product decision and regression tests.
- Material profiles, synthetic fixtures, and future real team interviews use the same result schema but are never mixed silently: source kind, consent, access policy, and missing-media states are visible to the recruiter.

## Complexity Tracking

| Deviation | Why needed | Simpler alternative rejected |
|---|---|---|
| Dedicated media range endpoint | Full recordings must remain private while supporting YouTube-like seeking | Public object URLs would leak recordings; whole-file downloads fail the UX requirement |
| Durable assessment orchestration | Current agent routes exist but candidate completion does not guarantee final assessment/report | Browser-triggered LLM calls expose secrets and lose retries/resume semantics |
| Explicit synthetic source kind | Demo needs ten complete rows without misrepresenting them as real candidates | Unmarked fixtures violate evidence and privacy requirements |
