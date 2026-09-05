# Data Model: Integrated Interview Runtime

## Existing authoritative entities to reuse

- `Vacancy`: role metadata and source document.
- `InterviewInvitation`: opaque token digest, vacancy link, candidate alias, expiry, consent/status, and question configuration.
- `InterviewSession`: one recording lifecycle for one invitation.
- `InterviewRecording` and chunks: continuous media plus ordered ten-second objects.
- `CandidateResponse`: question ID, start/end offsets, timeout marker, transcription status and text.
- `CodeAnswer`: language and source code associated with the same response as its spoken explanation.
- `InterviewFollowUpQuestion`: source response, transcript snapshot, depth/status, timestamps.
- Agent sessions/artifacts and ranking entries: evidence-linked internal evaluation.

## Configuration schema

### InterviewConfigurationSnapshot

- `schema_version`: positive integer.
- `blocks`: exactly one each of `hard_skills`, `soft_skills`, and `experience`, in display order.
- `live_coding_enabled`: boolean; when false, coding questions cannot appear.
- Validation: question IDs unique across all blocks; at least one total question; snapshot immutable after invitation issuance.

### QuestionBlock

- `key`: fixed category key.
- `title`: candidate-visible name.
- `position`: unique non-negative integer.
- `questions`: ordered list, possibly empty provided the overall interview is non-empty.

### ConfiguredQuestion

- `id`: stable UUID.
- `text`: non-empty prompt.
- `kind`: `spoken` or `coding`.
- `position`: unique within block.
- `time_limit_seconds`: null or bounded positive integer.
- `follow_up_enabled`: boolean.
- `language`: required for coding, absent for spoken.

## New presenter entities

### PresenterAsset

- `id`: UUID.
- `invitation_id`: owning invitation.
- `question_id`: configured or follow-up question identifier.
- `content_hash`: normalized text plus voice, portrait, TTS, and renderer versions.
- `question_text_snapshot`: exact synthesized text.
- `voice_id`, `tts_version`, `portrait_version`, `renderer_version`.
- `status`: `queued`, `audio_processing`, `audio_ready`, `avatar_processing`, `ready`, or `failed`.
- `audio_storage_key`, `video_storage_key`: nullable private object keys.
- `failure_stage`, `failure_reason`, `attempt_count`, and lifecycle timestamps.
- Constraints: unique active asset per invitation, question, and content hash; never store invitation secret.

### ProcessingJob

- `id`: UUID.
- `kind`: `transcription`, `runtime_assessment`, `presenter_audio`, `presenter_avatar`, or `final_assessment`.
- `entity_id`: target entity UUID.
- `status`: `pending`, `running`, `completed`, `retryable_failed`, or `terminal_failed`.
- Attempt and lifecycle fields plus bounded error code.
- Constraint: idempotency key prevents duplicate work for one kind and target version.

## Read models for cabinet

### InterviewResultSummary

- Invitation/session IDs, candidate alias, vacancy ID, lifecycle state, timestamps, duration.
- Processing summary with explicit pending/failed counts.
- Evidence-linked aggregate results only when available.

### InterviewResultDetail

- Summary plus ordered questions, responses, transcript status/text, recording offsets, code answer, follow-ups, and time-limited signed media URLs.
- Missing or pending data remains explicit; no mock defaults.

## State transitions

```text
Invitation: active -> consented -> in_progress -> completed

PresenterAsset:
queued -> audio_processing -> audio_ready -> avatar_processing -> ready
                    |             |              |
                    +-----------> failed <--------+
```

Once audio is ready, candidate playback may continue with a static portrait even if avatar rendering fails.
