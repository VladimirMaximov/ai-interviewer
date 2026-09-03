# Data Model: Asynchronous AI Interview

- **InterviewTemplate / InterviewQuestion**: approved, versioned six-question sequence; each
  question has text, order, required flag, and avatar asset reference.
- **InterviewInvitation**: candidate and template reference, one-way digest of the URL secret,
  expiry/revocation/submission timestamps, and status. The URL never contains candidate identity.
- **InterviewSession**: one per invitation; records consent, current question, and state
  `not_started → in_progress → submitted` (or expired/revoked). Submission is immutable.
- **CandidateResponse**: session/question reference, private object key, checksum, recording
  metadata, and transcription state `pending|processing|completed|failed`. Transcript segments
  retain source timing; failed transcription never creates text.
- **ReviewerAssignment**: maps recruiter or hiring manager to an interview.
- **ReviewDecision**: exactly one owner type: `ai_recommendation`, `recruiter_decision`, or
  `hiring_manager_decision`; AI may not create a final candidate outcome.
- **EvidenceReference**: decision-to-response link with transcript start/end timestamps and either
  a cited excerpt or `insufficient_information`.
