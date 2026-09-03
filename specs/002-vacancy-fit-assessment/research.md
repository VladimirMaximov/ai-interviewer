# Technical Research: Vacancy-aware Candidate Assessment and Feedback

## Source analysis: Napoleon IT competency framework

The repository source deck, [`NapoleonIT_Competency Framework.pptx.pdf`](../../NapoleonIT_Competency%20Framework.pptx.pdf),
contains a company-wide soft-skill matrix and role-specific professional matrices:

- four common competencies: Learn IT, Make IT, Drive IT, and Lead IT;
- graded hard-skill matrices for Software Engineer, QA Engineer, DevOps / Platform Engineer,
  Data Engineer, ML / LLM Engineer, Business Analyst, System Analyst, Full-stack Analyst,
  Project Manager, and Product Manager;
- a separate Architect progression (Architect, Senior Architect, Principal Architect);
- separate Tech Lead and Team Lead responsibility profiles;
- AI Impact as an explicit aspect in every professional or leadership profile.

Most individual-contributor matrices use Junior, Middle, and Senior anchors. The common matrix also
defines Lead / Manager anchors. Leadership pages describe expectation, decision scope, and impact
rather than reusing the Junior-to-Senior scale. The normalized product model therefore cannot assume
that every role has the same level vocabulary or that a leadership profile is merely a higher IC
score.

## Decision 1: Version the corporate framework as reference data

**Decision**: Normalize the deck into immutable `CompetencyFrameworkVersion`, `RoleProfile`,
`Competency`, and `LevelAnchor` records. Preserve the source wording, role-specific level scale, and
source-page provenance. A corrected or expanded framework is a new version; existing assessment
snapshots continue to reference the old version.

**Rationale**: The deck is an excellent company baseline but is not itself a runtime contract. A
versioned normalized form makes criteria addressable, testable, and auditable without flattening
Tech Lead, Team Lead, and Solution Architect into the same progression.

**Alternatives considered**:

- Put the entire deck text into every model prompt: rejected because it is difficult to validate,
  expensive, and easy to apply the wrong role column.
- Convert all roles to one universal numeric ladder: rejected because leadership and architecture
  use materially different level semantics.
- Copy only competency names: rejected because names without observable anchors are not a rubric.

## Decision 2: Use a draft-review-approve pipeline for vacancy context

**Decision**: Treat manager phrases, pasted text, uploaded documents, speech transcripts, and default
selections as `VacancyContextSource` records. Extract source fragments, propose structured vacancy
criteria, validate them, and require explicit manager approval before they become an immutable
`VacancyProfileVersion`.

Each approved criterion contains:

- stable ID and label;
- category: `must_have`, `priority`, or `additional`;
- link to zero or more corporate competencies;
- observable working behavior and expected depth;
- positive and negative anchors;
- accepted alternative evidence;
- an insufficient-information rule;
- weight within the vacancy-fit dimension;
- links to the questions capable of eliciting evidence;
- provenance pointing to manager source fragments or an explicit system suggestion.

**Rationale**: Free text is useful for authoring but unsafe as the final scoring contract. Review and
approval prevent silent interpretation drift and let the manager correct vague requests such as
"knows Kubernetes" into testable expectations.

**Alternatives considered**:

- Use keywords directly as evaluation criteria: rejected because keywords express neither depth nor
  acceptable evidence.
- Let the model update the profile during candidate assessment: rejected because candidates would
  no longer be compared under the same rules.
- Require managers to fill every structured field manually: rejected because it makes setup slow and
  discards the requested text/file/speech authoring workflow.

## Decision 3: Model "agent memory" as an explicit context snapshot

**Decision**: Do not use conversational memory as vacancy storage. At interview assignment, build an
immutable `AssessmentContextSnapshot` that pins framework, vacancy profile, rubric, question set,
aggregation policy, ranking policy, and candidate-feedback policy versions plus content hashes.

For each AI-assisted operation, assemble a bounded context bundle from authoritative records:

```text
system policy (code-owned, immutable)
    + approved vacancy snapshot (manager-owned data)
    + task-specific candidate evidence
    + output contract
```

Source files and manager text are placed only in data sections and are never concatenated into the
system policy. Cache keys include the operation type and every referenced version/hash. No candidate
answer or vacancy source is available to another vacancy unless explicitly referenced by an
authorized aggregate report.

**Rationale**: This gives the desired vacancy-specific "memory" while eliminating cross-vacancy
leakage, hidden state, and non-reproducible prompt history.

**Alternatives considered**:

- One long-lived assistant thread per manager: rejected because edits, access boundaries, and exact
  replay are difficult to audit.
- One global vector index for all vacancies: rejected for the first version because authorization and
  retrieval leakage are higher risks than retrieval scale.
- Pass only the latest vacancy text: rejected because older interviews must remain reproducible.

## Decision 4: Keep assessment dimensions orthogonal

**Decision**: Store and present at least four separate families of information:

1. `corporate_competency`: demonstrated behavior against the selected role framework;
2. `vacancy_fit`: evidence against manager-approved criteria for this vacancy;
3. `evidence_sufficiency`: coverage and confidence, outside the score scale;
4. `integrity_signal`: observed events for human inspection, never a score input.

Each assessed criterion uses an anchored ordinal result:

- `not_demonstrated` = 0;
- `partially_demonstrated` = 1;
- `demonstrated` = 2;
- `strongly_demonstrated` = 3;
- `insufficient_information` = no numeric value.

The framework target level remains a separate property. The ordinal result says how well the answer
demonstrates the selected anchor; it does not claim to measure a person's universal worth or exact
job grade.

**Rationale**: A candidate can demonstrate strong engineering competence but be a weak match for a
particular stack or project, and vice versa. Missing evidence is uncertainty, not failure.

**Alternatives considered**:

- One blended score: rejected because it hides whether a result comes from general capability,
  local preference, or missing data.
- Binary fit/no-fit per criterion: rejected because it loses partial evidence and makes calibration
  brittle.
- Ask an LLM for a final percentage: rejected because aggregation must be deterministic and
  reproducible.

## Decision 5: Aggregate deterministically and rank only compatible candidates

**Decision**: For each dimension, calculate a weighted mean only over criteria with numeric results
and report `evidence_coverage = assessed_weight / applicable_weight` alongside it. Never substitute
zero for `insufficient_information`.

The default ranking policy is versioned and fixed before candidate results exist:

1. candidates below the configured evidence-coverage floor appear in an `additional_review` group
   and receive no misleading ordinal position;
2. remaining candidates are ordered by vacancy-fit aggregate;
3. a configured secondary dimension, normally corporate-competency aggregate, is used only when
   the primary values differ within the policy's declared precision;
4. exact ties share a rank; response time, application time, names, and demographic proxies are not
   tie-breakers.

Only candidates with the same vacancy ID, vacancy-profile version, framework version, rubric version,
question-set version, and ranking-policy version enter one `RankingSnapshot`. Re-assessment produces
a new snapshot rather than rewriting an old one.

**Rationale**: This makes ranking useful for shortlist navigation without implying comparability
across jobs or disguising uncertainty as low skill.

**Alternatives considered**:

- Rank every candidate globally: rejected because scores are not calibrated across roles and
  vacancies.
- Rank low-evidence candidates at the bottom: rejected because absence of evidence is not negative
  evidence.
- Use application time as a final tie-breaker: rejected because it is unrelated to the stated job
  criteria and silently breaks equal ranking.

## Decision 6: Separate evaluator output, aggregator output, and human decisions

**Decision**: An evaluator may return criterion-level labels, evidence links, explanations, and
confidence. Deterministic application code validates evidence spans and calculates dimension
summaries. A report composer can summarize immutable results but cannot alter them. Recruiter,
technical-expert, and hiring-manager decisions are append-only records outside the assessment.

No score, missing-information state, rank, or integrity signal automatically creates `advance`,
`hold`, or `reject`.

**Rationale**: This preserves evidence-first behavior and allows disagreements to become calibration
data rather than invisible score edits.

**Alternatives considered**:

- Let the report generator choose the recommendation: rejected because prose generation would become
  an uncontrolled decision path.
- Store only the latest human decision in feedback: rejected because it conflates evaluation,
  communication, and decision ownership.

## Decision 7: Use append-only staged feedback

**Decision**: Replace the single mutable feedback concept with `FeedbackEntry` plus revisions. The
first entry has stage `post_async_assessment` and is initially an AI-assisted draft. A later entry has
stage `post_human_review` and is human-authored or human-confirmed. Further stages can be added without
changing the two-stage contract.

Published feedback is immutable. A correction is a new entry or revision linked to the prior
publication. Candidate-safe content includes assessment scope, strengths, growth areas, evidence
gaps, limitations, and next steps. Vacancy-fit totals, rank, weights, internal risks, integrity
signals, and hiring decisions remain internal.

**Rationale**: The candidate can receive useful feedback after the first technical stage and a more
informed update after human review without erasing what was communicated earlier.

**Alternatives considered**:

- Overwrite one feedback row: rejected because the current implementation loses stage history and
  makes corrections unauditable.
- Automatically publish model-generated personalized feedback: deferred until a separate safety and
  quality experiment; the first version requires a human publication action.
- Put the hiring decision in candidate feedback: rejected because decision and developmental
  feedback have different audiences and controls.

## Decision 8: Keep adapters replaceable and the first implementation narrow

**Decision**: Extend the existing modular monolith and SQLite adapter. Define ports for context-source
extraction, speech transcription, vacancy-profile drafting, criterion assessment, and feedback
drafting. The first runnable slice accepts direct text and UTF-8 `.txt`/`.md` files, accepts an
already-produced speech transcript, and uses deterministic test doubles for AI outputs. PDF/DOCX
extraction and live ASR plug into the same ports later.

**Rationale**: This exercises versioning, approval, isolation, scoring, ranking, and feedback now,
while preventing document parsing and provider setup from dominating the domain design.

**Alternatives considered**:

- Introduce separate services and queues immediately: rejected because current local scale does not
  justify operational complexity.
- Couple the domain to one model vendor or document parser: rejected because model/data constraints
  remain undecided and the repository requires provider portability.
- Exclude file and speech concepts entirely: rejected because they are part of the manager authoring
  journey; the port and source model must be stable even when the initial adapters are narrow.

## Decision 9: Validate quality with criterion-level and decision-level metrics

**Decision**: Frozen evaluation compares AI criterion labels with independent technical-expert labels
under the same context snapshot. Report exact agreement, weighted agreement for the ordinal scale,
macro-F1, evidence precision, evidence coverage, false pass, false reject, and the additional-review
rate. Vacancy-fit and corporate-competency metrics are reported separately. Human overrides are
captured as outcomes for calibration, not silently fed back into historical runs.

**Rationale**: Overall recommendation agreement alone cannot show whether the new vacancy context
helps, harms, or simply changes coverage.

**Alternatives considered**:

- Optimize only correlation with manager decisions: rejected because manager preference is not an
  independent ground truth and could import bias.
- Measure only average score error: rejected because ordinal labels, missing evidence, and asymmetric
  hiring errors need separate visibility.
