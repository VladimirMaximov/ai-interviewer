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

## Upload decision

The API validates the invitation and issues a short-lived upload grant limited to one response.
The browser uploads audio directly to private object storage, then confirms it with the API. This
avoids making the API a large-file relay and supports interruption recovery.
