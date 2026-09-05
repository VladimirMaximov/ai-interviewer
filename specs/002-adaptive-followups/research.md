# Decision Record: Asynchronous Adaptive Follow-ups

**Date**: 2026-09-04  
**Status**: Accepted for the MVP foundation; no clarification agent is enabled.

## Context

The interview must remain asynchronous for the candidate: they should be able to save an answer
and immediately proceed through the approved question sequence. At the same time, a later agent
must be able to request one focused factual clarification while the candidate is still in the
same interview. Waiting for transcription or model reasoning between questions would make the
candidate flow slow and fragile.

## Decision

1. One continuous private video-with-audio recording is divided into ordered 10-second fragments.
   The browser saves an answer as a pair of recording offsets and continues recording.
2. Once confirmed fragments fully cover an answer's end offset, its transcription starts in the
   background. This is independent of final interview submission.
3. A durable clarification queue stores one optional question per source response together with
   its transcript snapshot and lifecycle: `pending`, `ready`, `presented`, `answered`, `skipped`,
   or `failed`.
4. The candidate checks for queued clarifications after saving an answer. Any ready item is
   appended after the approved base sequence; it never replaces a base question or pauses the
   candidate while a decision is made.
5. The queue has an internal integration boundary that accepts only a completed transcript. No
   LLM, prompt, scoring logic, or automatic hiring outcome is enabled in this iteration.

## Consequences

- The candidate's next base question remains available without waiting for ASR or a future agent.
- A clarification can be available before the base sequence ends, but its earliest availability is
  bounded by fragment closure, upload confirmation, and transcription time.
- If transcription fails, the provider is unavailable, or its output is invalid, no clarification
  is shown. The candidate can still complete the interview.
- Every eventual clarification can be traced to the source response and exact transcript snapshot.
- This capability must not be used to score, reject, or otherwise make a personnel decision.

## Explicit non-goals

- Selecting or calling an LLM provider.
- Designing a prompt, an agent loop, or retries for agent output.
- Showing internal transcripts, reasoning, or hiring signals to the candidate.
- Reordering approved base questions or allowing the candidate to revisit prior questions.
