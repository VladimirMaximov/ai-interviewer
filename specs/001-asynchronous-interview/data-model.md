# Data Model: Asynchronous AI Interview

- **InterviewTemplate / InterviewQuestion**: approved, versioned six-question sequence; each
  question has text, order, required flag, and avatar asset reference.
- **InterviewInvitation**: candidate and template reference, one-way digest of the URL secret,
  expiry/revocation/submission timestamps, and status. The URL never contains candidate identity.
- **InterviewSession**: one per invitation; records consent, current question, and state
  `not_started → in_progress → submitted` (or expired/revoked). Submission is immutable.
- **InterviewRecording**: one logical private continuous video-with-audio recording per session;
  it records media metadata, a manifest checksum, start/end timestamps, and is never public.
- **InterviewRecordingChunk**: an ordered private 10-second video fragment belonging to one
  recording. It records sequence, time bounds, storage key, checksum, and upload confirmation;
  only a fragment is held in browser memory at a time.
- **InterviewTimelineEvent**: immutable event with session/question reference, event type,
  UTC timestamp, and `recording_offset_ms`. It records `recording_started`, `question_shown`,
  `answer_saved`, `next_question_clicked`, and `interview_submitted`.
- **CandidateResponse**: session/question reference plus `start_offset_ms` and `end_offset_ms`
  into the continuous recording, transcription state `pending|processing|completed|failed`, and
  transcript text. Failed transcription never creates text.
- **InterviewFollowUpQuestion**: an optional queued clarification with a source-response reference,
  transcript snapshot and lifecycle state `pending|ready|presented|answered|skipped|failed`; there
  is at most one active clarification for a source response. It is reserved for a future agent and
  never blocks the approved base sequence.
- **ReviewerAssignment**: maps recruiter or hiring manager to an interview.
- **ReviewDecision**: exactly one owner type: `ai_recommendation`, `recruiter_decision`, or
  `hiring_manager_decision`; AI may not create a final candidate outcome.
- **EvidenceReference**: decision-to-response link with transcript start/end timestamps and either
  a cited excerpt or `insufficient_information`.
