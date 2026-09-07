# Quickstart: Validate Vacancy-aware Assessment and Feedback

This guide is the acceptance path for the feature described in [spec.md](spec.md). It uses synthetic
aliases and text answers only. The entity rules are in [data-model.md](data-model.md), and the HTTP
payloads are defined in [contracts/openapi.yaml](contracts/openapi.yaml).

## Prerequisites

- Python 3.12 or newer.
- Repository root as the current directory.
- No real candidate name, resume, recording, transcript, or secret committed to the repository.
- A local manager key supplied at runtime.

## 1. Run the baseline gates

```bash
PYTHONPATH=tools/product-research python -m product_engineering "AI technical interview" --dry-run
PYTHONPATH=tools/product-research:prototypes/interview-platform python -m unittest discover -s tests -v
python -m compileall -q tools/product-research/product_engineering prototypes/interview-platform/interview_platform
```

Expected result: all existing pipeline and platform tests pass before feature-specific behavior is
evaluated.

## 2. Start the synthetic vacancy-assessment demo

```bash
export INTERVIEW_MANAGER_KEY='local-demo-secret'
export INTERVIEW_RECRUITER_KEY='local-recruiter-secret'
python -m interview_platform \
  --db-path /tmp/interview-platform-vacancy-assessment.sqlite3 \
  --seed-vacancy-assessment-demo
```

Expected result: the command prints manager and candidate URLs plus synthetic IDs for:

- one published competency-framework version;
- one Python vacancy;
- an approved vacancy-profile version;
- one assessment-context snapshot;
- at least three candidate aliases evaluated under the same snapshot.

The seed command must be idempotent and must never print a stored invitation-token digest or include
real personal data.

## 3. Validate vacancy profile authoring

In the manager portal:

1. Create a vacancy using the Software Engineer role and one target level.
2. Add one phrase such as "нужен опыт эволюции API без остановки клиентов".
3. Add one UTF-8 `.md` source that includes a second observable expectation.
4. Generate a profile draft from both sources.
5. Confirm that every proposed criterion contains category, depth, weight, positive/negative anchors,
   insufficient-information rule, question coverage, and provenance.
6. Try to add "уверенно звучит" as a criterion.
7. Try to approve one criterion after removing all question links.
8. Correct both blocking issues and approve the profile.

Expected result:

- input remains visibly classified as manager data rather than system instructions;
- the voice-confidence criterion and uncovered criterion block approval;
- approval produces an immutable version and content hash;
- editing after approval creates a new draft version instead of changing the approved one.

## 4. Validate the bounded vacancy context

Create an interview from the approved profile and note its assessment-context snapshot. Then publish a
new vacancy-profile version with different stack preferences.

Expected result:

- the existing interview continues to reference the original framework, vacancy profile, rubric,
  ranking policy, and feedback policy versions;
- a new interview can reference the new snapshot;
- no operation silently changes the old snapshot.

Run the isolation regression group:

```bash
python -m unittest -v tests.test_context_isolation tests.test_vacancy_profile
```

Expected result: the same answer evaluated under two vacancies has identical corporate-competency
results; only vacancy-fit criteria change. Prompt-injection-like text in a manager source cannot alter
the output contract or expose another vacancy.

## 5. Validate assessment dimensions and evidence

Submit a synthetic interview and create its initial assessment run. Open the manager assessment card.

Expected result:

- `corporate_competency` and `vacancy_fit` appear as separate sections and summaries;
- `baseline_recommendation.score` is `1`, `0`, or `-1`; its comment and evidence explain the
  recommendation, while `is_hiring_decision` always remains `false`;
- an explicit answer such as «Я ничего не хочу» produces `0` with the exact answer excerpt, and a
  vague or borderline result produces `-1` for manual review;
- every numeric label has a stored answer excerpt or time span;
- an unanswered criterion is `insufficient_information`, has no ordinal value, and reduces evidence
  coverage without contributing a zero;
- confidence and evidence coverage are not displayed as competency or fit scores;
- integrity events appear separately and do not change any result;
- an adapter response with an invalid excerpt fails the run atomically and exposes a safe error code.

Run deterministic assessment tests:

```bash
python -m unittest -v tests.test_assessment tests.test_assessment_repository
```

## 6. Validate compatible-only ranking

Build a ranking snapshot for the seeded candidates evaluated under the same snapshot. Repeat the
operation after shuffling input run IDs. Then add a run from the second vacancy-profile version.

Expected result:

- repeated calculations have identical scores, groups, ranks, and explanations;
- candidates below the evidence-coverage floor appear in `additional_review` without an ordinal rank;
- exact ties share one rank;
- vacancy fit is visible separately from corporate competency;
- the incompatible run is rejected and identifies the mismatching version field;
- no interview state or human decision changes when a ranking is created.

```bash
python -m unittest -v tests.test_ranking tests.test_decisions
```

## 7. Validate separate human decisions

As recruiter, technical expert, and hiring manager, append distinct decisions for one synthetic
interview. Make one decision disagree with the ranking order, then supersede only that role's decision.

Expected result:

- all role-specific records remain in history;
- the latest decision is resolved independently per role;
- neither assessment results nor ranking snapshots are modified;
- the candidate projection contains none of the decisions.

## 8. Validate two-stage candidate feedback

1. Complete an assessment and generate a `post_async_assessment` draft.
2. Open the candidate link before publication.
3. Edit and publish the draft as an authorized reviewer.
4. Create and publish a `post_human_review` entry.
5. Create a corrective publication linked to the first entry.

Expected result:

- before publication the candidate sees only a pending-review status;
- afterward the candidate sees published entries in sequence, including the correction;
- the earlier publication remains available in audit history;
- candidate-visible output includes scope, strengths, growth areas, evidence gaps, limitations, and
  next steps only;
- vacancy-fit totals, rank, weights, internal notes, integrity events, and decisions never appear.

```bash
python -m unittest -v tests.test_feedback_timeline tests.test_vacancy_assessment_api
```

## 9. Final full verification

```bash
PYTHONPATH=tools/product-research:prototypes/interview-platform python -m unittest discover -s tests -v
python -m compileall -q tools/product-research/product_engineering prototypes/interview-platform/interview_platform
git diff --check
```

Expected result: all tests pass, compilation succeeds, and the repository has no whitespace errors.
