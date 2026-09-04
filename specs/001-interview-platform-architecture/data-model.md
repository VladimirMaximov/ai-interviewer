# Data Model: Three-Role Interview Platform POC

## Interview

One synthetic candidate invitation and its lifecycle.

| Field | Type | Rules |
|---|---|---|
| id | string | Immutable staff-side identifier |
| candidate_alias | string | Required; synthetic in demo and tests |
| position_title | string | Required, at most 120 characters |
| invitation_token_digest | string | Unique SHA-256 digest; raw token is never persisted |
| status | enum | invited, in_progress, submitted, reviewed |
| evidence_type | enum | Always synthetic in this POC |
| consent_given_at / started_at / submitted_at | timestamp or null | Set by valid state transitions |
| created_at / updated_at | timestamp | UTC audit timestamps |

~~~text
invited --consent/start--> in_progress --complete--> submitted
~~~

Saving answers is allowed only while in progress. Role reviews do not modify candidate answers.

## Question and Answer

Question has an immutable interview id, prompt, positive position, and required flag. Answer belongs
to both an interview and question, uses capture kind text_stub, contains 1–10,000 characters, and
has no media reference in this slice.

## Recruiter Review

This record owns funnel-level review and candidate feedback. It is not a manager decision.

| Field | Type | Visibility / rule |
|---|---|---|
| id / interview_id | string | One current recruiter review per interview |
| candidate_summary | string | Candidate-visible only after publication |
| strengths | list[string] | Candidate-visible only after publication |
| risks | list[string] | Staff-only |
| next_steps | string | Candidate-visible only after publication |
| internal_notes | string | Staff-only |
| recruiter_decision | enum | advance, hold, reject; staff-only |
| assigned_manager | string or null | Controls manager access |
| publication_status | enum | draft or published |
| evidence | list[ReviewEvidence] | At least one verified item |
| version | integer | Increments on every save |
| published_at / updated_at | timestamp | Publication and audit timestamps |

Only a recruiter endpoint creates or changes this record. A published review cannot be changed back
to a draft.

## Manager Review

| Field | Type | Rules |
|---|---|---|
| id / interview_id | string | One current manager review per interview |
| manager_id | string | Must equal the recruiter assignment |
| manager_decision | enum | advance, hold, reject |
| notes | string | Required staff-only comment |
| reviewed_at | timestamp | UTC audit timestamp |

The manager can write this record only for an assigned interview. Reassignment immediately revokes
the previous manager's access and clears its stale current review. Recruiter and manager decisions
remain separate values; ai_recommendation is null in this POC.

## Review Evidence

| Field | Type | Rules |
|---|---|---|
| id / review_id | string | Belongs to one recruiter review |
| kind | enum | answer_excerpt or insufficient_information |
| question_id | string | Must belong to the reviewed interview |
| excerpt | string or null | Exact substring of the stored answer, or null for missing evidence |
| note | string | Required explanation |

## Access matrix

| Capability | Candidate | Recruiter | Manager |
|---|---:|---:|---:|
| Open own invitation and save answers | yes | no | no |
| List the whole interview funnel | no | yes | no |
| Create invitation and receive raw token | no | yes | no |
| Save/publish recruiter feedback | no | yes | no |
| Assign a manager | no | yes | no |
| View an unassigned interview | own only | yes | no |
| Save manager decision | no | no | assigned only |
| View internal decisions | no | yes | assigned only |

Candidate access uses the raw invitation token. Recruiter and manager use distinct runtime secrets.

## Transactional invariants

- Interview and questions are created atomically.
- Candidate token lookup uses only a digest at rest.
- Saving a recruiter review replaces its evidence and increments its version atomically.
- Manager assignment is checked in the application service, not only in the UI.
- Recruiter and manager reviews use different tables and domain entities.
- Candidate projections serialize only published safe fields.
