# Research: Unified Interview Demonstration Cabinet

## Decision 1: Treat the supplied material set as one vacancy plus candidate profiles

- **Decision**: Seed `Middle+ Python Developer` as the only confirmed real vacancy. Treat the PDFs in `materials/.../рандомные профили разрабов.zip` as synthetic or anonymized candidate profiles, not additional vacancies.
- **Rationale**: `Пример вакансии и вопросов.pdf` contains the explicit vacancy and six example questions. The QA notes identify Python developer as the pilot vacancy. The archive filenames identify developer profiles at different levels.
- **Alternatives considered**: Inventing a second vacancy; rejected because no second vacancy description or requirements were supplied.

## Decision 2: Use one entrance with bounded role behavior

- **Decision**: The root screen exposes recruiter, candidate, and manager choices. Recruiter is functional; candidate choice explains that a tokenized link is required; manager choice is a non-data-bearing “coming soon” placeholder in this phase.
- **Rationale**: It satisfies the requested unified entry without granting incomplete or unsafe access.
- **Alternatives considered**: Implementing a manager portal now; rejected because the user explicitly deferred it.

## Decision 3: Keep invitation tokens as the identity boundary

- **Decision**: Every candidate flow remains scoped by an opaque invitation token. Candidate display name and resume are stored against that invitation/session, never against a shared browser identity.
- **Rationale**: Multiple simultaneous interviews need isolation, independent lifecycle, and non-guessable links.
- **Alternatives considered**: One global demo candidate; rejected because it cannot support parallel runs or reliable leaderboard rows.

## Decision 4: Deliver video with HTTP range support and seekable timestamps

- **Decision**: Store metadata and signed/private media keys separately, expose a protected streaming response that honors byte ranges, and keep question/event offsets in milliseconds.
- **Rationale**: Recruiters need to start playback at a question or antifraud interval without downloading the complete recording first.
- **Alternatives considered**: Pre-cutting every answer into a separate file; retained only as a possible optimization because it duplicates media and complicates real interview uploads.

## Decision 5: Separate synthetic fixtures from real team interviews

- **Decision**: Add an explicit source kind and seed at least ten synthetic candidate rows with placeholder media, deterministic question intervals, assessments, reports, and reviewer-only antifraud events. Real team runs use the same entities with `real` source kind and require consent.
- **Rationale**: The demo must be complete immediately while preserving the distinction between test evidence and real participant data.
- **Alternatives considered**: Reusing real recordings as fixtures; rejected by privacy and repository evidence rules.

## Decision 6: Make the assessment orchestration durable and explicit

- **Decision**: After each stored transcript, enqueue or invoke answer assessment; after all required answers and conditional questions are complete, run integrity check and deterministic profile aggregation, then generate a recruiter report. Candidate UI does not make recruiter-only assessment calls directly.
- **Rationale**: Current code exposes the stages but does not connect candidate completion to the full agent pipeline. Durable stage status prevents a partial interview from appearing finalized.
- **Alternatives considered**: Running all LLM calls in the browser; rejected for secret exposure, authorization, and retryability.

## Decision 7: Preserve evidence-first scoring and human review boundaries

- **Decision**: Keep signed labels, exact evidence references, missing-information values, reviewer-only antifraud signals, and separate AI/recruiter/manager decisions. Do not score appearance, accent, emotion, or voice confidence.
- **Rationale**: These are repository domain constraints and are necessary for an auditable demonstration.
- **Alternatives considered**: A single opaque overall score; rejected because it cannot support question-level review or evidence links.

## Decision 8: Use a fixed demo access model for the current phase

- **Decision**: Retain the existing recruiter access mechanism for the demo and do not introduce a new identity provider in this feature. Manager and candidate role choices do not imply staff authentication.
- **Rationale**: The requested scope is a demonstration cabinet, while a production authentication migration would materially expand risk and scope.
- **Alternatives considered**: Full account registration/OIDC; deferred to a dedicated security feature.
