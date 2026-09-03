# Feature Specification: Adaptive Follow-up Questions

**Feature Branch**: `002-adaptive-followups`  
**Created**: 2026-09-04  
**Status**: Foundation implemented; clarification agent deferred

## User Scenarios & Testing

### User Story 1 - Continue without waiting (Priority: P1)

An invited candidate answers the approved base sequence without waiting for an AI analysis after
each answer. If an answer leaves a material fact unclear, the interview agent can prepare one
short optional follow-up and place it after the remaining base questions.

**Acceptance scenarios**:

1. Given a candidate saves an answer, when its transcription becomes available, then a follow-up
   may be prepared in the background without blocking the next base question.
2. Given a follow-up is prepared, when the candidate completes the base sequence, then the
   follow-up is presented with the same text, voice and recording flow as a base question.
3. Given no follow-up is needed or transcription fails, then the candidate can finish after the
   base questions without an invented question.

### User Story 2 - Preserve traceability (Priority: P1)

An interviewer integration can trace every agent-generated follow-up to the answer that prompted
it, the transcript version used, the agent decision and the candidate's resulting response.

## Functional Requirements

- **FR-001**: The system MUST persist the approved base question sequence independently of the
  browser interface.
- **FR-002**: The system MUST persist an agent follow-up with its source response, question text,
  lifecycle state and creation time.
- **FR-003**: The system MUST enforce a configurable maximum of one follow-up per base response
  for the initial release.
- **FR-004**: The system MUST never hold a candidate on a loading state while deciding whether a
  follow-up is needed.
- **FR-005**: A follow-up MUST be presented as an optional question and MUST not replace or alter
  a candidate's original response.
- **FR-006**: The system MUST retain the transcript and source-response reference used for an
  agent follow-up.
- **FR-007**: A failed transcript, unavailable agent, or invalid agent output MUST result in no
  follow-up rather than a fabricated question.
- **FR-008**: The agent MUST not make an automatic candidate outcome or score; it may only propose
  a clarifying question.
- **FR-009**: A saved response MUST become available for background transcription as soon as the
  confirmed recording covers its end, without waiting for interview completion.
- **FR-010**: Until a model provider and prompt policy are explicitly approved, the system MUST
  not invoke an agent; only validated internal integrations may enqueue a clarification.

## Key Entities

- **Interview Question**: An approved base prompt and its presentation order.
- **Clarification Request**: A pending, ready, presented, answered, skipped or failed optional
  follow-up linked to one source response.
- **Clarification Decision**: The bounded agent outcome: no follow-up or one validated prompt,
  with the transcript version and reason retained for traceability.

## Success Criteria

- **SC-001**: The next base question is available to a candidate within three seconds of saving an
  answer, whether or not an agent analysis is running.
- **SC-002**: Every generated follow-up is traceable to exactly one source response and transcript.
- **SC-003**: 100% of unavailable-agent and failed-transcript cases complete the base interview
  without blocking the candidate.

## Assumptions

- Follow-ups are appended after the base sequence in the initial release.
- The provider that decides whether a clarification is useful is pluggable and disabled by default
  until a model and prompt policy are selected.
- Follow-ups are short factual clarifications, not behavioural or appearance-based assessments.
