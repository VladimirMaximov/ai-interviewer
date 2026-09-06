# Data Model: Unified Interview Demonstration Cabinet

## Existing aggregates to extend

The implementation should extend the current hiring-context, interview, multi-agent, and
proctoring models rather than create a parallel result store.

## Entities

| Entity | Key fields | Rules |
|---|---|---|
| Vacancy | `id`, `title`, `description`, `requirements`, `manager_brief`, `version`, `status` | One seeded real vacancy is `Middle+ Python Developer`; manager brief is versioned with the vacancy. |
| Invitation | `id`, `vacancy_id`, `token_hash`, `expires_at`, `status`, `source_kind` | Token is opaque, stored hashed, unique, and scoped to one vacancy. `source_kind` is immutable: `synthetic` or `real`. |
| Candidate profile | `invitation_id`, `display_name`, `pseudonym`, `resume_text`, `consent_at` | Name and resume are supplied before starting; recruiter display uses pseudonym by default. |
| Interview session | `id`, `invitation_id`, `status`, `started_at`, `completed_at`, `last_activity_at` | One active session per invitation; transitions are monotonic and resumable. |
| Question response | `session_id`, `question_id`, `status`, `transcript`, `started_ms`, `ended_ms` | Question identity and intervals are immutable after finalization; absent timestamps are explicit. |
| Media asset | `session_id`, `object_key`, `content_type`, `byte_size`, `duration_ms`, `checksum` | Object is private; synthetic assets are placeholders and cannot be presented as real recordings. |
| Agent assessment | `response_id`, `criteria`, `evidence`, `follow_up`, `coding`, `status` | Every criterion has evidence or explicit insufficient evidence; retries are idempotent. |
| Candidate result | `session_id`, `readiness`, `coverage`, `confidence`, `summary`, `report`, `status` | Scores come from deterministic aggregation; recruiter and manager decisions remain separate. |
| Antifraud event | `session_id`, `kind`, `start_ms`, `end_ms`, `severity`, `review_status` | Visible as a review signal only; never changes the candidate score automatically. |
| Synthetic fixture | `invitation_id`, `fixture_key`, `dataset_version` | Marks all demo rows, media, timestamps, assessments, and reports as synthetic. |

## Relationships

`Vacancy 1—N Invitation 1—1 CandidateProfile 1—1 InterviewSession 1—N QuestionResponse`.
Each response may have one current assessment and many idempotent attempt records. A session
may have several media assets (for example, one final recording and upload parts), many
antifraud events, and at most one published candidate result/report.

## State transitions

```text
Invitation: created -> profile_pending -> ready -> in_progress -> completed
                         |                    |                 |
                         +-> expired          +-> cancelled     +-> failed
Session:    pending -> in_progress -> processing -> completed
                                      |             +-> review_required
                                      +-> failed (retryable)
Response:   pending -> recording -> uploaded -> transcribing -> assessed
                                                |              +-> assessment_failed
                                                +-> transcription_failed
```

Only backend services may move a session to `completed`. A result is published only after all
required responses are assessed, conditional follow-ups are resolved, and the integrity stage
has finished. A missing recording or timestamp keeps the relevant field explicitly incomplete;
it does not cause fabricated media or evidence.

## Validation and isolation

- Resolve every candidate request by the invitation token and verify its vacancy/session.
- Use transaction uniqueness for token hashes, session IDs, question IDs within a session, and
  fixture keys within a dataset version.
- Accept bounded UTF-8 display names and resume text; normalize whitespace but preserve the
  submitted text for audit.
- Require `0 <= start_ms < end_ms <= duration_ms` when duration is known.
- Authorize recruiter result/detail/media reads through the existing staff access mechanism.
- Never include raw invitation secrets in logs, reports, fixture files, or URLs beyond the
  opaque token itself.
