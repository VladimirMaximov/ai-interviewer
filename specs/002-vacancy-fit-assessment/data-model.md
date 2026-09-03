# Data Model: Vacancy-aware Candidate Assessment and Feedback

## Model boundaries

The feature introduces six related but independent boundaries:

1. corporate competency reference data;
2. manager-owned vacancy context;
3. immutable interview assessment context;
4. evidence-backed assessment and deterministic summaries;
5. compatible-candidate ranking and human decisions;
6. candidate/internal feedback history.

An `Interview` references these boundaries but does not own them. Deleting or editing a vacancy must
not rewrite a historical assessment, decision, or published feedback entry.

## CompetencyFrameworkVersion

An immutable, published normalization of the Napoleon IT competency framework.

| Field | Type | Rules |
|---|---|---|
| `id` | UUID string | Immutable primary identifier |
| `version` | positive integer | Unique within organization |
| `name` | string | Required; human-readable framework name |
| `status` | enum | `draft`, `published`, `retired` |
| `source_reference` | string | Required; repository path or controlled source identifier |
| `source_hash` | SHA-256 hex | Required; identifies exact source content |
| `content_hash` | SHA-256 hex | Required; canonical normalized-content hash |
| `created_by` | actor ID | Required |
| `created_at` | timestamp | Immutable UTC timestamp |
| `published_at` | timestamp/null | Required only for `published` or `retired` |

State transitions:

```text
draft -> published -> retired
```

Published content is immutable. Corrections create a new version.

## RoleProfile

Defines the level vocabulary and applicable competencies for one professional family.

| Field | Type | Rules |
|---|---|---|
| `id` | UUID string | Immutable |
| `framework_version_id` | UUID string | Required parent |
| `role_key` | snake_case string | Unique in framework version |
| `display_name` | string | Required |
| `profile_kind` | enum | `graded_ic`, `architecture`, `technical_leadership`, `people_leadership` |
| `description` | string | Required source-bounded summary |
| `level_keys` | ordered list[string] | Non-empty; role-specific vocabulary |
| `source_page` | positive integer | Page in source deck |

The initial normalized set contains Software Engineer, QA Engineer, DevOps / Platform Engineer,
Data Engineer, ML / LLM Engineer, Solution Architect, Business Analyst, System Analyst, Full-stack
Analyst, Project Manager, Product Manager, Tech Lead, and Team Lead. The general soft-skill profile is
attached to all roles but keeps its own Junior/Middle/Senior/Lead-or-Manager anchors.

## Competency and LevelAnchor

`Competency` is one independently assessed aspect. `LevelAnchor` describes observable behavior at a
role-specific level.

| Competency field | Type | Rules |
|---|---|---|
| `id` | stable string | Stable across framework versions when semantic meaning is unchanged |
| `framework_version_id` | UUID string | Required |
| `role_profile_id` | UUID string/null | Null for company-wide competencies |
| `dimension` | enum | `soft_skill`, `hard_skill`, `leadership` |
| `code` | snake_case string | Unique within role profile |
| `display_name` | string | Required |
| `description` | string | Required |
| `position` | positive integer | Unique within role profile and dimension |
| `source_page` | positive integer | Required provenance |

| LevelAnchor field | Type | Rules |
|---|---|---|
| `id` | UUID string | Immutable |
| `competency_id` | string | Required parent |
| `level_key` | string | Must be present in the role profile's `level_keys` |
| `level_order` | positive integer | Unique within competency |
| `behavior_text` | string | Required observable behavior |
| `decision_scope` | string/null | Used by leadership profiles when source provides it |
| `impact_scope` | string/null | Used by leadership profiles when source provides it |

Every published competency must have the full level set required by its role profile.

## Vacancy

The long-lived hiring position that owns context versions and ranking policies.

| Field | Type | Rules |
|---|---|---|
| `id` | UUID string | Immutable |
| `title` | string | Required, 1-120 characters |
| `role_profile_id` | UUID string | Must belong to selected framework version |
| `target_level_key` | string | Must be valid for the selected role profile |
| `status` | enum | `draft`, `active`, `closed` |
| `owner_actor_id` | actor ID | Required hiring-manager owner |
| `active_profile_version_id` | UUID string/null | Required before `active` |
| `active_ranking_policy_id` | UUID string/null | Required before ranking |
| `created_at` | timestamp | Immutable UTC timestamp |
| `updated_at` | timestamp | Updated on state change |

State transitions:

```text
draft --approved profile--> active --> closed
  ^             |
  +--new profile draft--+
```

Closing a vacancy prevents new invitations but preserves all versions and historical access.

## VacancyContextSource and SourceFragment

Stores manager input as provenance-bearing, untrusted data.

| VacancyContextSource field | Type | Rules |
|---|---|---|
| `id` | UUID string | Immutable |
| `vacancy_id` | UUID string | Required parent |
| `source_type` | enum | `default_selection`, `phrase`, `pasted_text`, `file`, `speech_transcript` |
| `display_name` | string | Required; original filename when applicable |
| `media_type` | string/null | Required for files |
| `original_reference` | opaque string/null | Controlled storage reference; never executable |
| `extracted_text` | string | Required after successful extraction |
| `content_hash` | SHA-256 hex | Hash of normalized extracted text |
| `status` | enum | `pending`, `ready`, `unsupported`, `invalid` |
| `created_by` | actor ID | Required |
| `created_at` | timestamp | Immutable |

| SourceFragment field | Type | Rules |
|---|---|---|
| `id` | UUID string | Immutable |
| `context_source_id` | UUID string | Required parent |
| `position` | positive integer | Source order |
| `text` | string | Required bounded fragment |
| `start_offset` / `end_offset` | integer | Valid range inside `extracted_text` |
| `classification` | enum | `verified_manager_input`, `system_suggestion` |

The first implementation limits uploaded file content to UTF-8 `.txt` and `.md`. File size,
fragment count, and extracted-text length have configured limits. A failed source never produces a
partially approved criterion.

## VacancyProfileVersion

An approved scoring context for one vacancy.

| Field | Type | Rules |
|---|---|---|
| `id` | UUID string | Immutable |
| `vacancy_id` | UUID string | Required parent |
| `framework_version_id` | UUID string | Required and immutable after creation |
| `version` | positive integer | Unique within vacancy |
| `status` | enum | `draft`, `validation_failed`, `approved`, `superseded` |
| `summary` | string | Required manager-readable description |
| `content_hash` | SHA-256 hex | Canonical criteria hash |
| `created_by` | actor ID | Required |
| `approved_by` | actor ID/null | Required for `approved` or `superseded` |
| `created_at` | timestamp | Immutable |
| `approved_at` | timestamp/null | Required for `approved` or `superseded` |

State transitions:

```text
draft --validate fails--> validation_failed --edit--> draft
draft --validate passes + manager approve--> approved --> superseded
```

Only one version may be the vacancy's active approved version. Superseded versions remain usable by
interviews that already pin them.

## VacancyCriterion

One vacancy-specific, observable expectation.

| Field | Type | Rules |
|---|---|---|
| `id` | stable string | Unique within profile version |
| `profile_version_id` | UUID string | Required parent |
| `code` | snake_case string | Required and unique within profile version |
| `display_name` | string | Required |
| `description` | string | Must describe observable job behavior |
| `category` | enum | `must_have`, `priority`, `additional` |
| `weight` | integer | 1-5; used only inside vacancy-fit dimension |
| `target_depth` | string | Required manager-approved expectation |
| `positive_anchors` | list[string] | At least one |
| `negative_anchors` | list[string] | At least one |
| `accepted_alternatives` | list[string] | May be empty but must be reviewed |
| `insufficient_information_rule` | string | Required |
| `linked_competency_ids` | list[string] | Zero or more compatible framework competencies |
| `source_fragment_ids` | list[UUID] | At least one, unless explicitly a system suggestion |
| `suggestion_confirmed_by` | actor ID/null | Required for a system-suggested approved criterion |
| `position` | positive integer | Unique in profile version |

Approval is rejected when a criterion contains prohibited trait categories, duplicates another
criterion, conflicts with the selected role/level, lacks anchors, or has no active question coverage.
`must_have` affects display and ranking policy but never creates an automatic rejection.

## QuestionRubricVersion and CriterionCoverage

Pins approved interview questions to both corporate and vacancy criteria.

| QuestionRubricVersion field | Type | Rules |
|---|---|---|
| `id` | UUID string | Immutable |
| `vacancy_profile_version_id` | UUID string | Required |
| `version` | positive integer | Unique within profile version |
| `status` | enum | `draft`, `approved`, `retired` |
| `content_hash` | SHA-256 hex | Required when approved |
| `approved_by` / `approved_at` | actor ID/timestamp | Required when approved |

| CriterionCoverage field | Type | Rules |
|---|---|---|
| `question_id` | UUID string | Required approved question |
| `criterion_kind` | enum | `corporate_competency`, `vacancy_fit` |
| `criterion_id` | stable string | Must resolve in pinned framework/profile |
| `coverage_intent` | string | Explains what evidence the question can elicit |

Each approved applicable criterion needs at least one active coverage link. One question may cover
multiple criteria, but assessment results remain independent.

## RankingPolicyVersion and FeedbackPolicyVersion

Policies are approved before candidate results are available.

| RankingPolicyVersion field | Type | Rules |
|---|---|---|
| `id` | UUID string | Immutable |
| `vacancy_id` | UUID string | Required |
| `version` | positive integer | Unique within vacancy |
| `status` | enum | `draft`, `approved`, `retired` |
| `primary_dimension` | enum | Default `vacancy_fit` |
| `secondary_dimension` | enum/null | Usually `corporate_competency` |
| `minimum_evidence_coverage` | decimal | 0-1 inclusive |
| `display_precision` | decimal rule | Fixed before approval |
| `required_context_match_fields` | list[enum] | Must include every version in compatibility key |
| `approved_by` / `approved_at` | actor ID/timestamp | Required when approved |

| FeedbackPolicyVersion field | Type | Rules |
|---|---|---|
| `id` | UUID string | Immutable |
| `vacancy_id` | UUID string | Required |
| `version` | positive integer | Unique within vacancy |
| `require_human_publication` | boolean | `true` in first implementation |
| `candidate_visible_sections` | list[enum] | Closed allowlist |
| `prohibited_candidate_sections` | list[enum] | Includes fit totals, rank, weights, signals, decisions |
| `approved_by` / `approved_at` | actor ID/timestamp | Required |

## AssessmentContextSnapshot

The bounded, immutable replacement for ambient agent memory.

| Field | Type | Rules |
|---|---|---|
| `id` | UUID string | Immutable |
| `vacancy_id` | UUID string | Required |
| `framework_version_id` | UUID string | Published version |
| `role_profile_id` | UUID string | Must belong to framework version |
| `target_level_key` | string | Valid for role profile |
| `vacancy_profile_version_id` | UUID string | Approved version |
| `question_rubric_version_id` | UUID string | Approved version compatible with profile |
| `ranking_policy_version_id` | UUID string | Approved for vacancy |
| `feedback_policy_version_id` | UUID string | Approved for vacancy |
| `context_hash` | SHA-256 hex | Hash of canonical referenced content and IDs |
| `created_at` | timestamp | Immutable |

The snapshot can be created only when all referenced versions are mutually compatible and approved.
It is never updated. An interview stores exactly one snapshot ID before invitation.

## Interview extension

Existing fields and state transitions remain. New fields are additive during migration.

| Field | Type | Rules |
|---|---|---|
| `vacancy_id` | UUID string/null | Required for the new vacancy-aware route; null only for legacy POC rows |
| `assessment_context_snapshot_id` | UUID string/null | Required before vacancy-aware invitation; immutable afterward |

An interview cannot start through the new route without a valid snapshot. Publishing a new vacancy
profile does not update an existing interview.

## AssessmentRun

One immutable attempt to assess a submitted interview.

| Field | Type | Rules |
|---|---|---|
| `id` | UUID string | Immutable |
| `interview_id` | UUID string | Submitted or reviewed interview |
| `context_snapshot_id` | UUID string | Must equal interview snapshot |
| `run_number` | positive integer | Unique within interview |
| `reason` | enum | `initial`, `manual_retry`, `model_change`, `policy_replay`, `calibration` |
| `status` | enum | `pending`, `running`, `completed`, `failed`, `invalidated` |
| `idempotency_key` | string | Unique per requested operation |
| `evaluator_id` | string | Adapter/provider identity |
| `model_id` | string/null | Exact model or deterministic-stub identifier |
| `prompt_hash` | SHA-256 hex/null | Required for AI-assisted run |
| `input_hash` | SHA-256 hex | Snapshot plus answer content hash |
| `output_hash` | SHA-256 hex/null | Required when completed |
| `failure_code` | string/null | Safe typed failure |
| `created_at` / `started_at` / `completed_at` | timestamps | State-aligned timestamps |

State transitions:

```text
pending -> running -> completed
                   -> failed --manual retry creates a new run-->
completed -> invalidated (administrative flag only; result retained)
```

Retries with the same idempotency key return the same run. A new evaluation reason creates a new run;
it never overwrites criterion results from an earlier run.

## CriterionAssessment and AssessmentEvidence

`CriterionAssessment` is the evaluator output after domain validation.

| CriterionAssessment field | Type | Rules |
|---|---|---|
| `id` | UUID string | Immutable |
| `assessment_run_id` | UUID string | Required completed parent |
| `dimension` | enum | `corporate_competency`, `vacancy_fit` |
| `criterion_id` | stable string | Must resolve in pinned snapshot |
| `label` | enum | `not_demonstrated`, `partially_demonstrated`, `demonstrated`, `strongly_demonstrated`, `insufficient_information` |
| `ordinal_value` | integer/null | 0-3 matching label; null only for insufficient information |
| `confidence` | decimal | 0-1; not part of score |
| `explanation` | string | Required; cannot introduce unsupported claims |
| `applicable_weight` | integer | Copied from approved rubric/profile; immutable |

| AssessmentEvidence field | Type | Rules |
|---|---|---|
| `id` | UUID string | Immutable |
| `criterion_assessment_id` | UUID string | Required parent |
| `kind` | enum | `support`, `counter_evidence`, `information_gap` |
| `question_id` | UUID string | Must belong to interview |
| `answer_id` | UUID/string | Must belong to question and interview |
| `excerpt` | string/null | Exact stored substring for support/counter-evidence |
| `start_ms` / `end_ms` | integer/null | Valid media/transcript interval when available |
| `note` | string | Required explanation |

Numeric labels require at least one `support` or `counter_evidence` item with a valid excerpt/time
span. `insufficient_information` requires one or more `information_gap` items and no ordinal value.
Evidence from resumes and interview answers, when added later, must use distinct evidence origins.

## AssessmentDimensionSummary

A deterministic derived record for exactly one dimension.

| Field | Type | Rules |
|---|---|---|
| `assessment_run_id` | UUID string | Composite identity with dimension |
| `dimension` | enum | `corporate_competency`, `vacancy_fit` |
| `score` | decimal/null | 0-100 weighted normalized score, null with no assessed weight |
| `assessed_weight` | positive integer/zero | Sum of weights with numeric labels |
| `applicable_weight` | positive integer | Sum of all applicable criterion weights |
| `evidence_coverage` | decimal | `assessed_weight / applicable_weight`, 0-1 |
| `label_counts` | map | Count of every label including insufficient information |
| `aggregation_policy_hash` | SHA-256 hex | Exact deterministic rule identity |

Summaries contain no human decision and cannot be directly edited.

## IntegritySignal

| Field | Type | Rules |
|---|---|---|
| `id` | UUID string | Immutable |
| `interview_id` | UUID string | Required parent |
| `signal_type` | enum/string | Observable event only, for example `tab_switch` |
| `occurred_at` | timestamp | Required |
| `metadata` | object | No inferred intent or verdict |

No relationship exists from `IntegritySignal` to score, ranking entry, or decision transition.

## RankingSnapshot and RankingEntry

`RankingSnapshot` is an immutable comparison of compatible completed runs.

| RankingSnapshot field | Type | Rules |
|---|---|---|
| `id` | UUID string | Immutable |
| `vacancy_id` | UUID string | Required |
| `ranking_policy_version_id` | UUID string | Approved policy |
| `compatibility_key` | canonical string/hash | Exact required version tuple |
| `assessment_run_ids` | ordered set[UUID] | Completed, valid, one per interview |
| `created_by` | actor ID | Required authorized staff actor |
| `created_at` | timestamp | Immutable |

| RankingEntry field | Type | Rules |
|---|---|---|
| `ranking_snapshot_id` | UUID string | Composite identity with run |
| `assessment_run_id` | UUID string | Must match snapshot compatibility key |
| `group` | enum | `ranked`, `additional_review` |
| `rank` | positive integer/null | Null for additional review; tied values share rank |
| `primary_value` | decimal/null | Derived from declared policy dimension |
| `secondary_value` | decimal/null | Derived only when configured |
| `evidence_coverage` | decimal | Used only for coverage-floor grouping |
| `explanation` | structured list | Criterion contribution and tie/coverage explanation |

The compatibility key includes vacancy, framework, role, target level, vacancy-profile,
question-rubric, ranking-policy, and aggregation-policy versions. Candidate alias, application time,
and personal attributes are never ordering keys.

## HumanDecision

An append-only decision owned by a person, never an assessment field.

| Field | Type | Rules |
|---|---|---|
| `id` | UUID string | Immutable |
| `interview_id` | UUID string | Required |
| `actor_id` | actor ID | Required |
| `actor_role` | enum | `recruiter`, `technical_expert`, `hiring_manager` |
| `decision` | enum | `advance`, `hold`, `reject`, `request_more_evidence` |
| `reason` | string | Required |
| `evidence_reference_ids` | list[UUID] | Optional, must belong to interview |
| `supersedes_decision_id` | UUID string/null | Same actor role and interview only |
| `created_at` | timestamp | Immutable |

The current decision for a role is the latest valid append-only record. It may disagree with ranking
or assessment and does not mutate either.

## FeedbackEntry, FeedbackRevision, and FeedbackEvidence

`FeedbackEntry` represents one timeline stage; revisions represent draft and publication history.

| FeedbackEntry field | Type | Rules |
|---|---|---|
| `id` | UUID string | Immutable |
| `interview_id` | UUID string | Required |
| `stage` | enum | `post_async_assessment`, `post_human_review` |
| `sequence` | positive integer | Unique timeline order within interview |
| `created_at` | timestamp | Immutable |

| FeedbackRevision field | Type | Rules |
|---|---|---|
| `id` | UUID string | Immutable |
| `feedback_entry_id` | UUID string | Required parent |
| `version` | positive integer | Unique within entry |
| `status` | enum | `draft`, `rejected`, `published` |
| `source_kind` | enum | `ai_assisted`, `human_authored`, `corrective` |
| `author_actor_id` | actor ID/string | Required; system actor allowed for draft only |
| `source_assessment_run_id` | UUID string/null | Required for post-assessment draft |
| `correction_of_revision_id` | UUID string/null | Published target when corrective |
| `assessment_scope` | list[string] | Candidate-visible |
| `strengths` | list[string] | Candidate-visible |
| `growth_areas` | list[string] | Candidate-visible |
| `evidence_gaps` | list[string] | Candidate-visible |
| `limitations` | list[string] | Candidate-visible |
| `next_steps` | string | Candidate-visible |
| `internal_notes` | string | Staff-only |
| `created_at` | timestamp | Immutable |
| `published_by` / `published_at` | actor ID/timestamp | Required only when published |

| FeedbackEvidence field | Type | Rules |
|---|---|---|
| `feedback_revision_id` | UUID string | Required parent |
| `assessment_evidence_id` | UUID string | Must resolve to the same interview |
| `section` | enum | Candidate-visible section supported by evidence |

A published revision is immutable. A draft can be rejected or published but cannot return from
published to draft. The candidate projection includes only published candidate-visible fields in
entry-sequence order. It never joins ranking, decision, integrity, weights, vacancy-fit summary, or
internal notes.

## AuditEvent

| Field | Type | Rules |
|---|---|---|
| `id` | UUID string | Immutable |
| `actor_id` | actor ID/string | Required |
| `actor_role` | enum/string | Required |
| `action` | closed string vocabulary | Approval, run, ranking, decision, publication, correction |
| `entity_type` / `entity_id` | string/UUID | Required target |
| `before_hash` / `after_hash` | SHA-256 hex/null | No raw sensitive payload |
| `metadata` | bounded object | Versions, reason, adapter IDs; no secrets |
| `occurred_at` | timestamp | Immutable UTC timestamp |

## Aggregate relationships

```text
CompetencyFrameworkVersion
  └─ RoleProfile ─ Competency ─ LevelAnchor

Vacancy
  ├─ VacancyContextSource ─ SourceFragment
  ├─ VacancyProfileVersion ─ VacancyCriterion
  ├─ QuestionRubricVersion ─ CriterionCoverage
  ├─ RankingPolicyVersion
  └─ FeedbackPolicyVersion

AssessmentContextSnapshot
  ├─ pins framework/profile/rubric/ranking/feedback versions
  └─ is referenced by Interview

Interview
  ├─ Questions ─ Answers
  ├─ AssessmentRun ─ CriterionAssessment ─ AssessmentEvidence
  │                 └─ AssessmentDimensionSummary
  ├─ IntegritySignal
  ├─ HumanDecision
  └─ FeedbackEntry ─ FeedbackRevision ─ FeedbackEvidence

RankingSnapshot ─ RankingEntry ─ AssessmentRun
```

## Transactional invariants

- Framework and vacancy-profile publication atomically validates content, records approver, freezes
  the hash, and updates the active pointer.
- Context-snapshot creation atomically verifies all version statuses and compatibility.
- A new vacancy-aware interview and its questions reference one snapshot in the same transaction.
- Assessment completion atomically validates every criterion/evidence item and writes both dimension
  summaries. Partial results never appear as completed.
- Ranking creation reads completed immutable summaries and writes the snapshot plus all entries in
  one transaction.
- Human decision append never updates assessment or ranking tables.
- Feedback publication writes a new immutable revision, publication metadata, evidence links, and
  audit event in one transaction.
- Candidate projections are built from an allowlisted feedback query rather than filtering a full
  manager object after serialization.

## Legacy migration mapping

- Existing interviews receive nullable `vacancy_id` and `assessment_context_snapshot_id`; legacy rows
  continue through the old synthetic-demo path.
- Existing one-row `feedback` data is exposed through a compatibility reader as a
  `post_human_review` entry. It is not automatically copied until migration tests verify evidence and
  publication semantics.
- Existing `manager_decision` becomes a legacy human-decision projection; all new decisions use
  append-only `HumanDecision` records.
- Existing answer-excerpt validation is retained and generalized for assessment and feedback
  evidence.
