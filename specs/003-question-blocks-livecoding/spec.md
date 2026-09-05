# Feature Specification: Question Blocks, Runtime Clarifications and Live Coding

**Feature Branch**: `003-question-blocks-livecoding`
**Created**: 2026-09-04
**Status**: Draft

## User Scenarios & Testing

### User Story 1 — Conduct an interview from question blocks (Priority: P1)

An interview creator supplies ordered thematic blocks such as experience, technical knowledge and
live coding. Each block contains its ordered questions and each question declares whether runtime
clarifications are permitted. The candidate sees the resulting ordered sequence, not the internal
policy.

**Why this priority**: An interview must not be hard-coded in the candidate UI and questions need
meaningful thematic ownership.

**Independent Test**: Create an invitation from two blocks and confirm the candidate receives their
questions in block and question order without policy flags.

**Acceptance Scenarios**:

1. **Given** valid blocks, **When** an invitation is created, **Then** its question order and block
   membership are preserved for that invitation.
2. **Given** a malformed block, duplicate question ID or empty prompt, **When** input is submitted,
   **Then** no invitation is created.

---

### User Story 2 — Request bounded runtime clarifications (Priority: P1)

After the candidate saves a spoken answer and proceeds, the service sends the question text and
completed answer transcript to a future external agent. The agent may respond with a confidence
and zero, one or two short clarification prompts for that base question. The candidate never waits
for this decision.

**Why this priority**: Focused follow-ups can resolve unclear technical evidence without turning
the interview into an unbounded conversation.

**Independent Test**: Save an eligible answer, verify one outbound agent request with only question
and transcript content, and verify that a stub decision of zero questions leaves the candidate
flow unchanged.

**Acceptance Scenarios**:

1. **Given** an eligible base answer with a completed transcript, **When** it becomes available,
   **Then** exactly one evaluation job is queued without blocking the next question.
2. **Given** an agent decision of two valid prompts, **When** the base sequence is complete,
   **Then** the two prompts appear in order and each is recorded as an answer.
3. **Given** an ineligible question, failed transcript, invalid decision or unavailable agent,
   **When** processing completes, **Then** no clarification appears and no candidate outcome is
   produced.

---

### User Story 3 — Complete a live-coding question (Priority: P2)

For a coding question, the candidate sees a code editor, selects a supported language and writes a
solution while the same continuous camera-and-microphone recording remains active. The code snapshot
is saved with its recording time interval when the candidate proceeds and is made available to the
future agent as answer text; it is not executed by this service.

**Why this priority**: Coding needs an evidence artifact distinct from speech while retaining the
same candidate progression and traceability.

**Independent Test**: Complete a coding question, reload its persisted answer through the internal
record, and verify the stored code and language are attached to that question.

**Acceptance Scenarios**:

1. **Given** a coding question, **When** it is shown, **Then** the candidate can type code and
   choose its language before continuing.
2. **Given** a non-empty code answer, **When** it is saved, **Then** its exact text, language and
   continuous-recording time interval are persisted without executing the code.

### Edge Cases

- The agent may return more than two prompts, duplicate text, a malformed confidence, or a prompt
  for a question that does not permit follow-ups; all such output is rejected.
- A transcript can finish after the candidate has already completed the base sequence; the service
  must not keep the candidate waiting or reopen a submitted interview.
- A coding answer with no code cannot be saved; a code answer is never evaluated or executed in the
  candidate application.
- Questions inside a block must remain immutable after an invitation is created.

## Requirements

### Functional Requirements

- **FR-001**: The input MUST accept an ordered list of question blocks with stable IDs, title,
  topic and ordered questions.
- **FR-002**: Every question MUST declare type `spoken` or `coding`; a spoken question may allow
  runtime clarifications and a coding question may not be executed by the service.
- **FR-003**: The service MUST persist the block/question configuration with the invitation and
  expose the candidate only the ordered prompts and question type.
- **FR-004**: The service MUST create at most one runtime evaluation job per eligible base spoken
  answer after its transcript is completed.
- **FR-005**: The outbound agent contract MUST contain only base-question text and answer transcript
  from this service; vacancy and resume context are owned by the calling integration.
- **FR-006**: The agent decision MUST contain a confidence in the range 0–1 and zero, one or two
  clarification prompts. A stub adapter MUST currently return zero prompts.
- **FR-007**: At most two clarification questions may be created for one base question. A
  clarification MUST NOT cause another clarification evaluation.
- **FR-008**: Runtime evaluation and its failures MUST NOT block recording, the next question or
  interview completion.
- **FR-009**: A coding answer MUST keep the continuous camera-and-microphone recording active and
  persist code text, selected language, and start/end offsets into that same recording. Code MUST
  NOT be run, compiled, linted or scored by this service.
- **FR-010**: The future agent MUST receive a coding answer only as text and language through the
  same explicit outbound contract.
- **FR-011**: No agent decision, confidence or internal rationale may create an automatic hiring
  decision or be exposed to the candidate.

### Key Entities

- **Question Block**: immutable thematic group with stable ID, title, topic and display order.
- **Block Question**: immutable question within a block, with prompt, type and clarification
  eligibility.
- **Runtime Evaluation Job**: one asynchronous request for a completed base answer with lifecycle,
  request/decision trace and no hiring outcome.
- **Clarification Decision**: validated confidence and zero to two prompts tied to one base answer.
- **Code Answer**: a candidate’s code text and selected language tied to a coding question.

## Success Criteria

### Measurable Outcomes

- **SC-001**: A candidate can receive and complete all questions from a configured three-block
  interview without a hard-coded prompt in the client.
- **SC-002**: The next base question is available within three seconds of saving an answer even if
  an evaluation job is queued.
- **SC-003**: 100% of accepted agent decisions create no more than two clarifications per base
  question; invalid decisions create none.
- **SC-004**: 100% of saved coding answers retain their text, selected language and synchronized
  recording interval without code execution.

## Assumptions

- The external integration enriches an outbound request with vacancy and resume data; this service
  does not fetch or store that context for the runtime agent.
- The first release appends valid clarification prompts after all base questions, as in the existing
  asynchronous candidate flow.
- The runtime adapter is a deterministic local stub returning `confidence: null` and no prompts
  until an agent provider and prompt policy are approved.
- A plain text editor is sufficient for the first live-coding release; collaboration, compilation,
  test execution and anti-cheat detection are outside its scope.
