# Research: Integrated Interview Runtime

## Decision 1: Preserve two frontends, share one visual foundation

- **Decision**: Keep `frontend/` for candidates and `frontend_ux/` for internal users. Publish shared CSS variables, fonts, spacing, controls, and status conventions from `packages/brand-tokens/`.
- **Rationale**: Candidate recording has media lifecycle and full-screen constraints that the cabinet does not. Shared tokens achieve visual continuity without merging incompatible build systems during the hackathon.
- **Alternatives considered**: Merge into one React application; manually duplicate CSS. Both enlarge regression risk or allow the visual systems to drift.

## Decision 2: Main backend and PostgreSQL are authoritative

- **Decision**: Map the cabinet to `backend/app` endpoints and existing PostgreSQL entities. Remove runtime dependence on `backend_ux/interview.db` and replace UI mocks with explicit loading, empty, pending, and failed states.
- **Rationale**: The main backend already owns invitations, recordings, code, transcripts, adaptive questions, assessments, and object storage.
- **Alternatives considered**: Synchronize SQLite with PostgreSQL or expose two APIs. Both create identity and consistency failures.

## Decision 3: Snapshot interview configuration per invitation

- **Decision**: Store a normalized, immutable copy of the three blocks and their questions on invitation creation.
- **Rationale**: Editing a vacancy later must not alter an interview already sent to a candidate.
- **Alternatives considered**: Read the live vacancy configuration throughout the interview. This makes recordings impossible to reproduce reliably.

## Decision 4: XTTS v2 followed by MuseTalk

- **Decision**: Use the existing persistent XTTS v2 integration for mixed Russian/English speech. Feed the produced waveform unchanged into MuseTalk with the approved portrait to render lip-synced video.
- **Rationale**: XTTS already exists in the repository and handles multilingual text better than the Russian-only default. MuseTalk was validated in the Kaggle prototype and fits the available NVIDIA T4 path.
- **Alternatives considered**: Browser speech, Silero, keyframe mouth animation, and PersonaLive. They are inconsistent, weaker for English, not speech-driven, or excluded due compute uncertainty.

## Decision 5: Durable queued generation with graceful fallback

- **Decision**: Persist a presenter-asset job in PostgreSQL, enqueue it through Redis, and process the GPU queue with concurrency one. Audio becomes independently usable as soon as XTTS completes. Avatar failure produces a static-portrait fallback.
- **Rationale**: API requests remain short, jobs can retry, duplicate work can be deduplicated, and T4 memory usage stays bounded.
- **Alternatives considered**: Generate synchronously in FastAPI or run an in-process executor. Both are fragile under restart and block requests.

## Decision 6: Warm known questions, generate adaptive questions on demand

- **Decision**: Queue assets for configured questions after invitation creation. Queue follow-up media as soon as runtime evaluation creates the follow-up.
- **Rationale**: It hides generation latency while retaining true runtime behavior for agent-created prompts.
- **Alternatives considered**: Generate every question only when displayed or pre-render all possible follow-ups.

## Decision 7: Demo identity without password authentication

- **Decision**: Candidate access remains invitation-token based. Internal endpoints retain configured recruiter/manager actor headers during this feature; the UI receives those values from deployment configuration, not a password form.
- **Rationale**: This matches explicit scope while avoiding the current false impression that an unverified `localStorage` user is authenticated.
- **Alternatives considered**: Preserve SHA-256 demo passwords or build full authentication now.
