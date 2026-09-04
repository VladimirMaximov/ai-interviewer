# Data Model: Session-scoped Multi-agent Candidate Matching

## Boundaries

One `AgentSession` belongs to exactly one invitation and one primary vacancy. It pins the latest
resume available when created, the current approved manager brief when present, and the policy and
compatibility versions. Session-owned artifacts may reference only this invitation's responses.
Vacancy ranking may combine sessions only when all compatibility fields match.

## AgentSession

| Field | Meaning |
|---|---|
| `id` | Stable session identifier |
| `invitation_id` | Candidate application; unique for the active POC session |
| `vacancy_id` | Primary vacancy |
| `interview_session_id` | Existing candidate interview session, nullable before consent |
| `resume_id` | Pinned resume version, nullable |
| `resume_version` / `resume_hash` | Reproducible resume input |
| `manager_brief_id` / `manager_brief_version` / `manager_brief_hash` | Optional approved wishes |
| `vacancy_hash` | Pinned vacancy source |
| `policy_version` | Strong-pool and grade policy |
| `criteria_version` | Question/criterion compatibility version |
| `scale_version` | `signed_criterion_v1` |
| `aggregation_version` | Deterministic profile formula |
| `input_hash` | Canonical hash of all pinned inputs |
| `status` | `active`, `ready`, or `failed` |
| `created_by`, `created_at`, `updated_at` | Audit metadata |

Validation:

- invitation and vacancy must exist and be linked;
- resume, when pinned, must belong to the invitation and vacancy;
- manager brief, when pinned, must be the approved version for the vacancy;
- pinned IDs and hashes never change.

## AgentOperation and AgentRun

`AgentOperation` is one idempotent requested stage. Its unique key is
`(agent_session_id, purpose, idempotency_key)` and it stores `input_hash`, status, successful artifact
ID, and timestamps.

`AgentRun` is one provider attempt under an operation. It stores attempt number, contract/provider/
model/prompt versions, input/output hashes, output payload for audit, terminal status, failure code,
and timestamps. At most one successful artifact can satisfy an operation.

Operation states:

```text
running -> succeeded
        -> failed -> running (new attempt)
```

Run states:

```text
running -> succeeded
        -> invalid_output
        -> provider_failed
```

## AgentArtifact

An immutable, validated output with:

- session and operation IDs;
- kind/purpose;
- schema version;
- canonical payload;
- content hash;
- creation time.

Supported artifact kinds:

- `resume_relevance`;
- `question_plan`;
- `answer_assessment`;
- `candidate_profile` (deterministic);
- `alternative_vacancy_match`;
- `integrity_check`.

Multiple `answer_assessment` artifacts may exist, one per stored response and idempotency key. Profile
creation selects the current successful set explicitly.

## Resume relevance payload

`ResumePosition` keeps every explicit job/project separate with position ID, employer, role, period,
project, responsibilities, skills, achievements, and one or more IDs from the immutable resume
evidence catalog. Missing subfields stay null or empty; they are never inferred.

`ResumeClaim`:

- claim ID and type;
- normalized subject and one or more resume evidence IDs;
- verification status: `unverified`, `supported`, `contradicted`, or `insufficient_information`;
- source resume ID/hash.

`ExperienceMatch`:

- experience label and resume evidence IDs;
- requirement ID and origin (`vacancy` or `manager_brief`);
- relevance in `[0, 1]`;
- confidence in `[0, 1]`;
- explanation;
- related position IDs;
- related claim IDs.

## Question plan payload

`QuestionSelection` contains:

- stable question ID;
- prompt;
- kind: `baseline` or `personalized`;
- one or more `CriterionDefinition` objects;
- source claim IDs for personalized questions;
- confirmed manager field keys for manager-requested personalized questions;
- selection reason.

`CriterionDefinition` declares criterion ID, title, dimension, weight, and expected positive/negative
signals. Baseline question IDs and order are derived from the pinned criteria version and do not vary
between sessions of the same vacancy compatibility key.

## Answer assessment payload

`CriterionObservation` contains:

- response, question, and criterion IDs;
- declared dimension;
- label and exact allowed value;
- confidence;
- explanation;
- evidence list with an exact ID from the answer evidence catalog and evidence kind.

Evidence catalogs are deterministic, source-owned projections with stable IDs and verbatim text.
Agents return only IDs. Raw agent outputs are persisted unchanged; candidate/recruiter views resolve
the selected IDs back to source text separately.

Allowed label/value pairs:

| Label | Value |
|---|---:|
| `contradicted` | `-1` |
| `weak` | `-0.5` |
| `neutral` | `0` |
| `supported` | `0.5` |
| `strong` | `1` |
| `insufficient_information` | `null` |

## CandidateProfile payload

- selected answer-assessment artifact IDs;
- criterion summaries with non-null means and evidence IDs;
- dimension summaries with values and coverage;
- overall readiness and overall coverage;
- strong-pool eligibility and reason codes;
- integrity-review flag;
- compatibility key;
- `is_hiring_decision = false`.

The compatibility key is the canonical hash of vacancy ID, vacancy hash, criteria version, scale
version, aggregation version, and policy version.

## RankingSnapshot and RankingEntry

`RankingSnapshot` stores vacancy, compatibility key, ordered profile IDs, input hash, and creation
time. `RankingEntry` stores snapshot/profile/session IDs, one-based rank, overall value, coverage,
and deterministic tie-break key. Neither entity references or changes invitation status.

## Alternative vacancy match payload

- target vacancy ID/title/hash;
- normalized candidate and target grades (`unknown`, `intern`, `junior`, `middle`, `senior`, `lead`);
- compatibility status: `compatible` or `manual_comparison_required`;
- fit value when compatible;
- matched terms, assessed criterion IDs, and supporting candidate evidence IDs;
- gaps;
- explanation;
- publication eligibility and reason code.

Only active vacancies other than the primary vacancy are included. A session failing strong-pool
eligibility receives an empty matches list and a reason code.

## Integrity observation payload

- status: `consistent`, `unverified_claim`, `contradiction_detected`, or
  `manual_integrity_review`;
- resume claim/evidence reference;
- answer evidence reference;
- explanation and clarification question;
- confidence;
- `is_restriction = false`.

An integrity artifact cannot contain restriction or blacklist fields.

## RestrictionDecision

| Field | Meaning |
|---|---|
| `id` | Decision ID |
| `invitation_id` | Candidate application |
| `decision_type` | `verified_misrepresentation`, `restricted`, `blacklisted`, or `cleared` |
| `reason` | Required human-authored reason |
| `evidence_references` | Required stored references except for `cleared` |
| `created_by` / `created_at` | Human actor and time |
| `expires_at` | Optional expiry |
| `supersedes_id` | Optional prior decision replaced by this record |

The current effective restriction is the latest non-expired decision in a valid supersession chain.
`cleared` removes the effective restriction without deleting history. Agent operations cannot insert
this entity.

## CandidateFeedbackOutput and CandidateFeedbackRelease

`CandidateFeedbackOutput` is an immutable `candidate_feedback_v1` agent artifact. It stores the
source profile artifact ID, candidate-facing headline and summary, evidence-linked strengths,
growth areas with practical actions, resume/interview alignment, an optional allowed alternative,
next steps, limitations, and `is_hiring_decision=false`. Internal rank, pool, integrity, restriction,
and anti-fraud fields are not part of its contract.

`CandidateFeedbackRelease` separates generation from delivery:

| Field | Meaning |
|---|---|
| `id` | Release ID |
| `invitation_id` / `agent_session_id` | Exact candidate/vacancy scope |
| `feedback_artifact_id` | Immutable validated LLM artifact |
| `status` | `draft` or `published` |
| `created_by` / `created_at` | Recruiter who requested the draft and creation time |
| `published_by` / `published_at` | Required human publisher and publication time |

The candidate endpoint resolves only the latest `published` release. It converts internal evidence
references to the candidate's own excerpts and derives the displayed 0–10 score deterministically
from the pinned signed readiness value. A draft never appears in the candidate projection. An
alternative vacancy is rechecked for active status immediately before publication.

## Privacy and deletion

- Candidate-facing serializers never read ranking or integrity artifacts and never expose
  restriction data. Restriction state may only suppress an unpublished alternative.
- Agent session projections identify the application by opaque IDs and recruiter-owned alias only.
- Deleting source candidate data must delete or tombstone session artifacts according to the
  product retention policy; immutable audit hashes must not retain recoverable PII.
- Tests and examples use synthetic text only.
