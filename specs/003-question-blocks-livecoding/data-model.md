# Data Model

- **InvitationQuestionBlock**: `id`, `title`, `topic`, `position` and ordered question snapshot.
- **InvitationQuestion**: `id`, `block_id`, `position`, `text`, `kind` and clarification policy.
- **RuntimeEvaluationJob**: one per eligible base response with status, timestamps, nullable
  confidence and failure-safe decision metadata.
- **CodeAnswer**: `response_id`, `language`, `source_code`, `start_offset_ms`, `end_offset_ms` and
  `saved_at`; its offsets refer to the same continuous video-with-audio recording as spoken answers.
- **InterviewFollowUpQuestion**: source response and sequence; at most two active rows per source.
