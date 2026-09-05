# Research: Bounded Runtime Clarifications

## Decisions

- Persist an invitation-level JSON block snapshot; it preserves order and avoids a premature
  authoring-portal dependency.
- Queue evaluation only after a spoken transcript completes, so the outbound contract contains text
  rather than raw media.
- Use a deterministic stub that returns zero prompts and makes no provider call.
- Reject more than two prompts, blank/duplicate prompts or invalid confidence. Clarifications never
  cause another evaluation.
- Use a plain-text code editor. Persist source and language but never execute the source.

The outbound request contains only `question_text`, `answer_text`, `answer_kind` and optional
`language`. Vacancy and resume context are explicitly outside this service.
