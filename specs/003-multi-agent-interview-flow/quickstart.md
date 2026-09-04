# Quickstart: Session-scoped Multi-agent Candidate Matching

## Prerequisites

- Python 3.12+
- backend dependencies installed
- PostgreSQL and object storage from `docker-compose.yml` for the full local flow
- recruiter and manager API keys configured
- `OPENAI_API_KEY` and `MULTI_AGENT_MODEL` configured; every semantic agent stage calls the LLM
- only synthetic vacancy, resume, and answer text

## 1. Run baseline gates

```bash
python -m unittest discover -s tests -v
PYTHONPATH=backend python -m unittest discover -s backend/tests -v
python -m compileall -q product_engineering interview_platform backend/app
```

Expected: existing and new suites pass with injected fake Responses clients and never make network
calls. Runtime agent stages do not have a deterministic fallback.

## 2. Apply the additive migration

```bash
docker compose up -d
PYTHONPATH=backend alembic -c backend/alembic.ini upgrade head
```

Expected: current vacancy, resume, manager-brief, and interview tables remain intact; agent session,
operation, run, artifact, ranking, and restriction tables are added.

## 3. Create synthetic source records

Use the existing vacancy, invitation, consent, resume, upload, and transcription flow documented in
`backend/README.md`. Approve manager wishes if desired. Ensure at least one candidate response has a
completed transcript and its `question_id` comes from the generated question plan.

## 4. Create the isolated agent session

```bash
curl -X POST \
  http://127.0.0.1:8000/recruiter/vacancies/VACANCY_ID/applications/INVITATION_ID/agent-session \
  -H 'X-Recruiter-Key: local-recruiter-key' \
  -H 'Idempotency-Key: agent-session-001'
```

Expected: response pins vacancy/resume/approved-brief hashes and all contract/policy versions.
Replaying the same request returns the same session.

## 5. Analyze resume and build questions

```bash
curl -X POST \
  http://127.0.0.1:8000/recruiter/vacancies/VACANCY_ID/applications/INVITATION_ID/agent-session/resume-analysis \
  -H 'X-Recruiter-Key: local-recruiter-key' \
  -H 'Idempotency-Key: resume-analysis-001'

curl -X POST \
  http://127.0.0.1:8000/recruiter/vacancies/VACANCY_ID/applications/INVITATION_ID/agent-session/question-plan \
  -H 'X-Recruiter-Key: local-recruiter-key' \
  -H 'Idempotency-Key: question-plan-001'
```

Expected: resume matches cite exact resume excerpts; the question plan contains a stable baseline and
bounded personalized questions linked to resume claims.

The candidate client reads only the safe question projection; criteria, weights, selection reasons,
integrity notes, and rankings are omitted:

```bash
curl http://127.0.0.1:8000/candidate/CANDIDATE_TOKEN/questions
```

## 6. Assess a stored answer

```bash
curl -X POST \
  http://127.0.0.1:8000/recruiter/vacancies/VACANCY_ID/applications/INVITATION_ID/agent-session/answer-assessments \
  -H 'X-Recruiter-Key: local-recruiter-key' \
  -H 'Idempotency-Key: answer-assessment-001' \
  -H 'Content-Type: application/json' \
  -d '{"response_id":"RESPONSE_ID"}'
```

Expected: each numeric observation cites an exact transcript substring. A criterion with no evidence
uses `insufficient_information` and `null`.

## 7. Finalize and inspect ranking

```bash
curl -X POST \
  http://127.0.0.1:8000/recruiter/vacancies/VACANCY_ID/applications/INVITATION_ID/agent-session/finalize \
  -H 'X-Recruiter-Key: local-recruiter-key' \
  -H 'Idempotency-Key: finalize-profile-001'

curl \
  http://127.0.0.1:8000/recruiter/vacancies/VACANCY_ID/ranking \
  -H 'X-Recruiter-Key: local-recruiter-key'
```

Expected: profile math is deterministic, coverage is separate, ranking contains only compatible
profiles, and alternative vacancies appear only when strong-pool eligibility and the pinned grade
distance policy pass. Unknown or non-comparable grades yield manual comparison, not a fabricated
fit score.

## 8. Generate, review, and publish candidate feedback

Generate an evidence-linked draft after finalization:

```bash
curl -X POST \
  http://127.0.0.1:8000/recruiter/vacancies/VACANCY_ID/applications/INVITATION_ID/agent-session/candidate-feedback \
  -H 'X-Recruiter-Key: local-recruiter-key' \
  -H 'Idempotency-Key: candidate-feedback-001'
```

Before publication, `GET /candidate/CANDIDATE_TOKEN/feedback` returns `pending_review` and no draft
content. After a recruiter reviews the response, publish the returned release ID:

```bash
curl -X POST \
  http://127.0.0.1:8000/recruiter/vacancies/VACANCY_ID/applications/INVITATION_ID/agent-session/candidate-feedback/RELEASE_ID/publish \
  -H 'X-Recruiter-Key: local-recruiter-key'

curl http://127.0.0.1:8000/candidate/CANDIDATE_TOKEN/feedback
```

Expected: the candidate receives the 0–10 interview score, useful strengths, concrete growth areas,
experience alignment, next steps, and at most one active allowed alternative. Rank, pool,
integrity/restriction records, model confidence, and internal evidence IDs are absent. Closing the
recommended vacancy before publication returns a conflict and requires a fresh review.

## 9. Validate integrity and human-only restrictions

Use synthetic resume text claiming a technology and an answer explicitly denying experience with the
same technology. Finalization should produce `contradiction_detected` or
`manual_integrity_review`, but no restriction.

An authorized recruiter may then append a human decision:

```bash
curl -X POST \
  http://127.0.0.1:8000/recruiter/applications/INVITATION_ID/restrictions \
  -H 'X-Recruiter-Key: local-recruiter-key' \
  -H 'Content-Type: application/json' \
  -d '{
    "decision_type":"restricted",
    "reason":"Synthetic reviewer-confirmed inconsistency",
    "evidence_references":["ARTIFACT_ID"]
  }'
```

Expected: the decision records the human actor and does not modify scores or agent artifacts. A later
`cleared` decision supersedes it without deleting history.

## 10. Final verification

```bash
PYTHONPATH=backend python -m unittest backend.tests.unit.test_multi_agent_harness -v
PYTHONPATH=backend python -m unittest backend.tests.integration.test_multi_agent_api -v
PYTHONPATH=backend python -m unittest backend.tests.integration.test_multi_agent_migration -v
PYTHONPATH=backend python -m unittest backend.tests.unit.test_multi_agent_scale -v
```

Expected: session isolation, exact evidence, deterministic profile/rank, eligibility, integrity
observation, human restriction history, and a 1,000-profile ranking below two seconds all pass.
