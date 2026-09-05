# Feature Specification: Integrated Interview Runtime

**Feature Branch**: `main`

**Created**: 2026-09-05

**Status**: Draft

**Input**: Unite the recruiter/manager cabinet and candidate interview into one working prototype while retaining two purpose-built UIs, applying one visual language, and generating multilingual speech and a lip-synced avatar at runtime. Password authentication is out of scope.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Configure and launch an interview (Priority: P1)

A recruiter uses the cabinet to define a vacancy and three question blocks, creates a candidate invitation, and receives a working private link. Opening that link starts the existing candidate journey with exactly the configured questions.

**Why this priority**: It closes the largest current gap: cabinet data and candidate interviews presently live in separate demonstrations.

**Independent Test**: Create a synthetic vacancy in the cabinet, copy its invitation link, complete one interview through that link, and verify that the session belongs to the same vacancy and invitation.

**Acceptance Scenarios**:

1. **Given** a vacancy with hard skills, soft skills, and experience blocks, **When** the recruiter creates an invitation, **Then** the system returns a one-time candidate link containing no user identifier.
2. **Given** a valid invitation, **When** the candidate opens it, **Then** the preparation screen shows the configured block and question counts without revealing the first question.
3. **Given** an expired, invalid, or completed invitation, **When** it is opened, **Then** no interview data is exposed and the candidate receives a clear terminal message.

---

### User Story 2 - Complete a visually consistent interview (Priority: P2)

A candidate moves from the preparation screen into the existing recording experience without a visual break between products. The candidate UI adopts the cabinet's Napoleon IT visual language while preserving its camera-first layout, accessibility, recording reliability, live coding, progress, timers, and completion screen.

**Why this priority**: The product must feel like one trustworthy service even though candidate and internal workflows remain separate applications.

**Independent Test**: Compare both UIs against the shared visual tokens and complete a three-block interview containing spoken and coding questions on desktop without a second permission request.

**Acceptance Scenarios**:

1. **Given** successful camera and microphone checks, **When** the candidate starts, **Then** media continues without another permission prompt and the first question appears only after start.
2. **Given** any configured question, **When** it is active, **Then** block progress, question progress, time limit, camera preview, spoken prompt, and applicable coding workspace remain usable.
3. **Given** the final answer is saved, **When** processing continues in the background, **Then** the candidate sees a final confirmation asking them to await recruiter contact, not internal processing details.

---

### User Story 3 - Hear a runtime-generated interviewer (Priority: P2)

The candidate hears every question in natural multilingual speech and sees a consistent interviewer portrait whose lip motion follows the generated speech. Preconfigured questions may be warmed ahead of time; dynamically generated follow-ups are synthesized during the interview.

**Why this priority**: Runtime generation is required for adaptive questions and is the visible differentiator of the hackathon prototype.

**Independent Test**: Present one Russian question containing English technical terms and one newly generated follow-up; verify that both receive intelligible audio and synchronized lip motion without manual phonetic spelling.

**Acceptance Scenarios**:

1. **Given** a mixed Russian/English technical question, **When** it is presented, **Then** all meaningful words are spoken intelligibly without manually rewritten pronunciation text.
2. **Given** a newly generated follow-up, **When** it becomes ready, **Then** its audio and avatar are generated automatically and playback starts once both are usable.
3. **Given** avatar generation is delayed or fails, **When** the question is ready, **Then** the interview continues with generated audio and a static portrait rather than blocking the candidate.

---

### User Story 4 - Review real interview results (Priority: P3)

A recruiter opens a vacancy in the cabinet and sees real interview sessions instead of mock candidates, including completion state, recordings, question-aligned transcripts, coding submissions, runtime follow-ups, and evidence-linked assessments.

**Why this priority**: It completes the feedback loop but is not required to demonstrate candidate capture and runtime avatar generation.

**Independent Test**: Complete a synthetic interview and open it from the cabinet; every displayed answer, code snapshot, timestamp, and media link must originate from that session.

**Acceptance Scenarios**:

1. **Given** a completed interview, **When** its candidate card is opened, **Then** real transcript segments and coding submissions are aligned to their questions and recording offsets.
2. **Given** processing is incomplete, **When** the result is opened, **Then** each pending or failed artifact has an explicit status and mock content is never substituted.
3. **Given** an assessment, **When** a score or conclusion is shown, **Then** it links to supporting transcript evidence or a timestamp and does not evaluate protected or appearance-related characteristics.

### Edge Cases

- A question has no time limit, an empty optional block, or live coding is disabled.
- The candidate denies or later revokes camera or microphone permission.
- A follow-up arrives after the UI has already advanced or the same completion event is retried.
- Runtime speech succeeds but avatar generation fails, or generated media arrives out of order.
- A question is repeated, contains long source-code fragments, or mixes Cyrillic and English abbreviations.
- The interview is refreshed, opened concurrently, expires, or was already completed.
- Processing is pending when the recruiter opens the result.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The service MUST use one authoritative vacancy, invitation, interview, response, transcript, code-answer, follow-up, and assessment dataset across both UIs.
- **FR-002**: The cabinet and candidate experience MUST remain separate entry points optimized for their respective users.
- **FR-003**: The cabinet MUST create and edit three named question blocks with variable question counts, spoken or coding question type, optional time limit, order, and follow-up eligibility.
- **FR-004**: The service MUST create an opaque, expiring candidate invitation associated with a vacancy configuration snapshot.
- **FR-005**: Candidate access MUST rely on the invitation secret; password registration and password login are outside this feature.
- **FR-006**: The first question MUST remain hidden until media checks pass and the candidate explicitly starts the interview.
- **FR-007**: Existing continuous camera/audio capture, ten-second chunk upload, question-boundary timestamps, live-coding capture, monitoring events, and automatic timeout submission MUST remain functional.
- **FR-008**: Both UIs MUST use shared brand colors, typography, spacing, controls, progress patterns, and status language while retaining layouts appropriate to each workflow.
- **FR-009**: Every presented question MUST have runtime-capable synthesized speech supporting Russian sentences containing English technical terminology.
- **FR-010**: Every presented question SHOULD have a lip-synchronized avatar generated from the approved portrait and synthesized speech.
- **FR-011**: Avatar failure MUST degrade to audio plus a static portrait and MUST NOT prevent answering or recording.
- **FR-012**: Known questions MUST be eligible for background warming after invitation creation; adaptive questions MUST use the same generation interface on demand.
- **FR-013**: Generated media MUST be scoped to the authorized invitation, tracked by state, and reusable without duplicate generation for identical question content and voice/avatar configuration.
- **FR-014**: The candidate MUST NOT wait indefinitely for runtime media; a bounded fallback path MUST allow the interview to continue.
- **FR-015**: The cabinet MUST display real sessions and artifacts and MUST NOT silently substitute mock candidates, transcripts, scores, or videos.
- **FR-016**: Candidate assessments MUST be evidence-first and MUST NOT automatically reject candidates or score appearance, accent, emotion, or voice confidence.
- **FR-017**: Password-based authentication, password storage, account recovery, and organization-level permissions MUST NOT be implemented in this feature.
- **FR-018**: Automated tests MUST cover contract validation, malformed inputs, retries, idempotency, media fallback, and the end-to-end synthetic interview path.

### Key Entities

- **Vacancy**: The role being interviewed for and its current description.
- **Interview Configuration Snapshot**: Immutable three-block question configuration used by one invitation.
- **Question Block**: One of hard skills, soft skills, or experience; contains ordered questions.
- **Question**: Spoken or coding prompt with order, optional time limit, follow-up eligibility, and generation identity.
- **Invitation**: Expiring opaque access link connecting a candidate alias and configuration snapshot.
- **Interview Session**: One candidate run with lifecycle, recording clock, and completion state.
- **Response**: Question-aligned recording interval and transcript; a coding response also references its code answer.
- **Generated Presenter Asset**: Versioned speech and avatar output for one question, voice, portrait, and renderer configuration.
- **Processing Job**: Durable state for transcription, assessment, speech, or avatar work, including attempts and failure information.
- **Assessment Artifact**: Evidence-linked observations and scores available to internal reviewers.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A recruiter can configure a synthetic vacancy, create a link, and start its candidate interview in under five minutes without command-line database changes.
- **SC-002**: 100% of questions shown in a completed test correspond to the configuration snapshot associated with its invitation.
- **SC-003**: In ten repeated desktop test runs, at least nine reach the first question after one permission flow and preserve continuous recording through completion.
- **SC-004**: Preconfigured-question presentation begins within two seconds for at least 95% of warmed assets under the target demo load.
- **SC-005**: A newly generated follow-up begins audio/avatar presentation within fifteen seconds for at least 90% of demo runs; all remaining successful-audio cases continue with a static portrait.
- **SC-006**: Reviewers can retrieve every completed response with its question, transcript status, recording offsets, and coding content where applicable, with no mock substitution.
- **SC-007**: Mixed Russian/English test prompts are intelligible to at least four of five internal reviewers without phonetic source rewrites.
- **SC-008**: Candidate-facing screens contain no internal transcription, model, confidence, queue, or infrastructure terminology outside an explicitly enabled debug mode.

## Assumptions

- The hackathon deployment uses the available Linux server with a Tesla T4 16 GB GPU, 32 GB system memory, and local SSD storage.
- The existing candidate recording workflow, PostgreSQL data, object storage, GigaAM transcription option, XTTS integration, and avatar portrait are reused.
- One simultaneous active interview is the guaranteed demonstration target; limited additional concurrency may queue GPU work.
- Recruiter/manager identity is supplied by trusted demo configuration or temporary actor headers. Full authentication is a later feature.
- Stable network handling beyond existing retry behavior and long-term retention policy are not expanded in this feature.
- The cabinet and candidate applications may be built separately but are served under one public domain.
