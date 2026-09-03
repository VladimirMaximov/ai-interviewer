# Feature Specification: Asynchronous AI Interview

**Feature Branch**: `001-asynchronous-interview`

**Created**: 2026-09-03

**Status**: Draft

**Input**: User description: "Create an asynchronous AI-led interview: a secure invitation link,
a browser interview screen, an avatar that speaks questions, candidate audio recording and
audio-to-text conversion, and responses and evidence for recruiter and hiring-manager review.
Do not automatically reject candidates or assess accent, emotion, or voice confidence."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Complete an invited interview (Priority: P1)

An invited candidate opens their unique link, understands the consent and recording notice,
answers a sequence of spoken questions in the browser, reviews their progress, and completes the
interview without creating an account.

**Why this priority**: This is the candidate-facing value on which all later review depends.

**Independent Test**: A test candidate can use a valid invitation to complete every question and
see a clear completion confirmation; a reviewer can see the resulting completed interview.

**Acceptance Scenarios**:

1. **Given** a candidate has a valid unused invitation link, **When** they open it, **Then** they
   see the role context, recording notice, consent choice, and a way to begin.
2. **Given** a candidate has consented and begun, **When** a question starts, **Then** the avatar
   presents the question audibly and the matching text is available to the candidate.
3. **Given** the candidate has recorded an answer, **When** they choose to continue, **Then** the
   answer is attached to that question and the next question is shown.
4. **Given** the candidate has answered all required questions, **When** they submit the interview,
   **Then** they see confirmation that it was received and can no longer alter submitted answers.

---

### User Story 2 - Recover from an interrupted interview (Priority: P2)

A candidate whose browser is closed or whose connection fails can safely resume an unfinished
interview using the same valid invitation without losing answers that were already saved.

**Why this priority**: Audio recording is sensitive to browser and network interruptions; recovery
prevents unnecessary candidate drop-off.

**Independent Test**: A test candidate records an answer, interrupts the session, returns through
the invitation, and finds the saved answer and correct next action.

**Acceptance Scenarios**:

1. **Given** an interview is in progress and an answer has been saved, **When** the candidate
   returns through the same valid invitation, **Then** the completed answer remains available and
   the candidate resumes at the first unfinished question.
2. **Given** microphone permission is denied or unavailable, **When** the candidate attempts to
   record, **Then** they receive a plain-language explanation and can retry after correcting it.

---

### User Story 3 - Review interview evidence (Priority: P3)

An authorized recruiter or hiring manager reviews a completed interview question by question,
listens to answers where permitted, reads their text versions, and sees the source evidence used
in any AI-generated recommendation.

**Why this priority**: The feature must support accountable human evaluation rather than replace
it.

**Independent Test**: An authorized reviewer opens a completed interview and can trace each shown
evidence item to a question, candidate answer, and transcript location.

**Acceptance Scenarios**:

1. **Given** a completed interview, **When** an authorized reviewer opens it, **Then** they see
   each question, its answer, its text version, and completion state.
2. **Given** an AI-generated recommendation is available, **When** a reviewer views it, **Then**
   it is separated from recruiter and hiring-manager decisions and cites answer evidence.

### Edge Cases

- An expired, revoked, already-completed, or malformed invitation link must not reveal interview
  content or candidate data; the visitor receives a safe next-step message.
- If a candidate's audio cannot be converted to text, the saved answer remains identifiable as
  awaiting processing or requiring retry; no invented transcript is displayed.
- If audio playback, avatar presentation, or recording fails, the candidate receives a clear retry
  path and the system preserves previously saved answers.
- If the candidate tries to submit with required unanswered questions, the system identifies each
  missing question before submission.
- If a reviewer lacks assignment to the candidate, the interview and its evidence are inaccessible.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST create a unique, revocable invitation link for a designated
  candidate and interview.
- **FR-002**: The system MUST prevent an invalid, expired, revoked, or completed invitation link
  from exposing interview content or candidate data.
- **FR-003**: The candidate experience MUST present a recording and data-use notice and require an
  affirmative consent choice before recording begins.
- **FR-004**: The system MUST present each interview question through an avatar's spoken delivery
  and provide the question text in the browser.
- **FR-005**: The candidate MUST be able to start, stop, review completion of, and replace an
  unsent audio response for the current question.
- **FR-006**: The system MUST save each confirmed response against its question before allowing the
  candidate to continue, and MUST preserve saved responses if the session is interrupted.
- **FR-007**: The system MUST convert each saved audio response to text, retain a clear association
  between audio, text, question, and interview, and explicitly show processing failure or absence
  of text.
- **FR-008**: The system MUST allow a candidate to submit only after all required questions have
  responses, and MUST record an immutable submitted state.
- **FR-009**: The system MUST limit completed-interview review to the assigned recruiter and hiring
  manager, subject to their role permissions.
- **FR-010**: The reviewer view MUST show questions, submitted answers, text versions, and any
  evidence references used in a recommendation.
- **FR-011**: The system MUST keep AI recommendations, recruiter decisions, and hiring-manager
  decisions as separate records.
- **FR-012**: The system MUST NOT automatically reject a candidate or produce a score based on
  appearance, accent, emotion, or voice confidence.
- **FR-013**: The system MUST provide a candidate-facing failure message and retry path when
  recording, question delivery, or text conversion cannot complete.

### Key Entities

- **Interview Invitation**: A time-limited, revocable candidate access grant tied to one
  interview.
- **Interview Session**: The candidate's in-progress or completed set of interview questions and
  responses.
- **Interview Question**: A prompt in the interview sequence, including its presentation order and
  whether an answer is required.
- **Candidate Response**: The audio answer, its text conversion status and content, timestamps,
  and submission relationship to one question.
- **Evidence Reference**: A traceable link from a reviewer-visible recommendation to a specific
  response and transcript location.
- **Review Decision**: A separate AI recommendation, recruiter decision, or hiring-manager
  decision associated with the completed interview.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: At least 90% of candidates who begin an interview with working microphone permission
  complete all required questions without human support in pilot testing.
- **SC-002**: At least 95% of saved candidate responses remain available after a simulated browser
  close and return through a valid invitation.
- **SC-003**: For at least 95% of completed responses, reviewers can open the associated text
  version or see an explicit processing-status message within one minute of opening the interview.
- **SC-004**: In review testing, 100% of displayed AI recommendation evidence can be traced by a
  reviewer to a specific question and response location.
- **SC-005**: 100% of test attempts using expired, revoked, malformed, or already-completed links
  do not expose interview questions, responses, or candidate identity.

## Assumptions

- The first release is an asynchronous browser experience: the avatar presents preconfigured
  questions; it is not a live two-way video meeting.
- Each candidate receives a single secure link and does not need a separate account for the first
  release.
- Invitation lifetime, replacement limits, deletion and retention periods, and consent wording
  will be selected before production release according to the applicable privacy policy.
- Audio availability, avatar provider, text-conversion provider, frontend technology, and detailed
  accessibility requirements are technical planning decisions, not part of this specification.
- The existing project will provide or define authentication and assignment data for recruiter and
  hiring-manager access.
