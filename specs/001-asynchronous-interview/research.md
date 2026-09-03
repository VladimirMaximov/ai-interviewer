# Research: Asynchronous AI Interview

## Chosen stack

- **Frontend**: React + TypeScript + Vite. It is a focused browser application for microphone
  permissions, recorder state, resilient uploads, and the reviewer view; server rendering is not
  needed for invitation-only MVP flow.
- **Backend**: FastAPI, as required by the project constitution.
- **Persistent data**: PostgreSQL; **audio blobs**: private S3-compatible object storage (MinIO
  locally). Audio is not stored in PostgreSQL.
- **Recording**: browser MediaRecorder. It is widely available and records a media stream obtained
  from microphone permission. [MDN](https://developer.mozilla.org/en-US/docs/Web/API/MediaRecorder)
- **Transcription**: local `whisper.cpp` is the MVP baseline because interview answers will
  normally exceed GigaAM v3's 25-second direct-transcription limit. It keeps candidate audio in
  project infrastructure and offers a local CLI for transcription. [whisper.cpp official
  repository](https://github.com/ggml-org/whisper.cpp) GigaAM `v3_e2e_rnnt` and RouterAI remain
  comparison adapters only; adoption requires a frozen synthetic long-answer benchmark covering
  technical vocabulary, accuracy, and latency. [GigaAM official repository](https://github.com/salute-developers/GigaAM)
- **Question voice**: `gpt-4o-mini-tts` behind an adapter.
- **Avatar**: a licensed neutral illustrated animated avatar with pre-generated question speech;
  do not use a streaming video-avatar vendor in MVP.

## Why not a real-time avatar

The interview is asynchronous: no human needs live media delivery. A streaming avatar introduces
WebRTC, added cost, and another sensitive-media vendor without improving the core flow. Keep avatar,
TTS, ASR, and storage behind project-owned adapters so providers can later be changed.

## Upload and background-processing decision

The browser keeps one continuous 720p video-with-audio recording and uploads private 10-second
fragments directly to object storage under short-lived scoped grants. The API stores each answer
as start/end offsets in that recording and records the candidate's explicit save/next action as a
timeline event. This avoids a large-file relay, bounds browser memory, and preserves one
continuous evidentiary recording.

An answer is transcribed in the background as soon as confirmed fragments cover its end offset;
the candidate proceeds to the next approved question without waiting for transcription. A failed
transcript has no candidate-visible error and does not invent text or a follow-up question.

## Deferred adaptive follow-up decision

The MVP keeps an internal, traceable queue for at most one optional clarification per source
response. A queued clarification retains the response reference and transcript snapshot, is shown
only after the approved base sequence, and uses the same presentation and recording path as a base
question. The clarification-model provider and prompt policy are deliberately **not implemented**
yet: an unavailable provider results in no clarification and never blocks completion or produces a
candidate score/outcome. The detailed decision record is in
[`../002-adaptive-followups/research.md`](../002-adaptive-followups/research.md).
