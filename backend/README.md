# Backend: local speech recognition

The default speech-to-text provider is local `whisper.cpp` with the multilingual `small` model.
Candidate audio is passed to the local backend process and is not sent to a cloud transcription
provider. This is the baseline because candidate answers are normally longer than 25 seconds.

## Local setup

## Full local demo

In three terminals from the repository root:

```bash
docker compose up -d
PYTHONPATH=backend alembic -c backend/alembic.ini upgrade head
PYTHONPATH=backend python backend/scripts/create_demo_invitation.py
```

Install backend dependencies once with `pip install -e ./backend`, then run the API with
`PYTHONPATH=backend uvicorn app.main:app --reload`. In another terminal run `npm --prefix frontend run dev`.
Open the URL printed by `create_demo_invitation.py`. It is synthetic, expires after 24 hours, and is intended only for local testing.

## Vacancy and resume matching API

Set `INTERVIEW_RECRUITER_KEY`, then upload one vacancy as the raw request body. UTF-8 text,
Markdown, DOCX, and PDF are accepted up to 5 MiB. The service extracts bounded text and persists its
hash and provenance; it does not publish the original file.

```bash
curl -X POST http://127.0.0.1:8000/recruiter/vacancies \
  -H 'X-Recruiter-Key: local-recruiter-key' \
  -H 'X-Vacancy-Title: Backend developer' \
  -H 'X-Document-Filename: vacancy.pdf' \
  -H 'Idempotency-Key: vacancy-upload-001' \
  -H 'Content-Type: application/pdf' \
  --data-binary @vacancy.pdf
```

Create a separate candidate link for that vacancy. The plaintext token is returned once and only
its SHA-256 digest is stored.

```bash
curl -X POST http://127.0.0.1:8000/recruiter/vacancies/VACANCY_ID/invitations \
  -H 'X-Recruiter-Key: local-recruiter-key' \
  -H 'Content-Type: application/json' \
  -d '{"candidate_alias":"candidate-001","expires_in_hours":72}'
```

The candidate first accepts the existing consent flow and then uploads a resume through the same
secret link. Re-uploading with a new idempotency key creates a new immutable version; downstream
context always selects the latest version.

```bash
curl -X POST http://127.0.0.1:8000/candidate/CANDIDATE_TOKEN/consent

curl -X POST http://127.0.0.1:8000/candidate/CANDIDATE_TOKEN/resume \
  -H 'X-Document-Filename: resume.pdf' \
  -H 'Idempotency-Key: resume-upload-001' \
  -H 'Content-Type: application/pdf' \
  --data-binary @resume.pdf
```

The recruiter may upload the resume for an application before the candidate opens the invitation.
This uses recruiter authentication and records `uploaded_by_role=recruiter` in the immutable resume
version. A later candidate upload remains possible after consent and creates the next version.

```bash
curl -X POST \
  http://127.0.0.1:8000/recruiter/vacancies/VACANCY_ID/applications/INVITATION_ID/resume \
  -H 'X-Recruiter-Key: local-recruiter-key' \
  -H 'X-Document-Filename: resume.pdf' \
  -H 'Idempotency-Key: recruiter-resume-upload-001' \
  -H 'Content-Type: application/pdf' \
  --data-binary @resume.pdf
```

Recruiters can inspect all invitations/resume versions matched to one vacancy and retrieve the
allowlisted context for one candidate only:

```text
GET /recruiter/vacancies/{vacancy_id}/applications
GET /recruiter/vacancies/{vacancy_id}/applications/{invitation_id}/agent-context
```

`agent-context` contains the vacancy, the latest resume, an optional approved manager brief, and
the candidate's own interview transcripts. Every free-text source is explicitly marked untrusted,
and a deterministic `context_hash` pins the exact input. Its policy states that resume content is
claim context only, missing evidence is not zero, interview scores require answer evidence, and no
automatic hiring decision is permitted.

Install `ffmpeg` and build the `whisper-cli` executable. Download a multilingual Whisper GGML
model, then configure its explicit local path:

```bash
git clone https://github.com/ggml-org/whisper.cpp.git
cd whisper.cpp
cmake -B build
cmake --build build --config Release
sh ./models/download-ggml-model.sh small
```

Set these environment variables only when overriding defaults:

```bash
TRANSCRIPTION_PROVIDER=whisper_cpp
WHISPER_CPP_BINARY=/absolute/path/to/whisper-cli
WHISPER_CPP_MODEL=/absolute/path/to/ggml-small.bin
```

The input must be converted to the format required by the installed `whisper-cli` version (the
current upstream CLI documents 16-bit WAV input); the upload pipeline will perform that conversion
before transcription.

GigaAM v3 (`v3_e2e_rnnt`) and RouterAI are optional benchmark adapters, not production defaults.
They may replace the baseline only after comparison on synthetic technical answers longer than
25 seconds, with recorded transcription accuracy and latency.

## Manager brief agent and editable form API

The manager flow turns free-form wishes into a versioned form. It uses the OpenAI Responses API
with a strict Pydantic structured output, following the official
[Structured Outputs guide](https://developers.openai.com/api/docs/guides/structured-outputs).
Manager text is passed as untrusted user data. Every extracted value carries source fragment IDs
and exact quotes. The agent is not allowed to propose or infer unstated requirements: fields absent
from the manager's text are omitted from `fields` and remain blank in the form. Missing fields do
not block approval.

Configure the provider and manager API key in the environment:

```bash
OPENAI_API_KEY=...
OPENAI_BASE_URL=https://api.openai.com/v1
MANAGER_BRIEF_MODEL=gpt-5-mini
MANAGER_BRIEF_MAX_ATTEMPTS=3
INTERVIEW_MANAGER_KEY=...
INTERVIEW_MANAGER_ID=hiring-manager
```

After applying Alembic migrations, create a draft for the vacancy UUID:

```bash
curl -X POST http://127.0.0.1:8000/manager/vacancies/00000000-0000-0000-0000-000000000001/brief-drafts \
  -H 'Content-Type: application/json' \
  -H 'X-Manager-Key: local-manager-key' \
  -H 'Idempotency-Key: vacancy-brief-001' \
  -d '{"source_text":"Ищем middle backend-разработчика. Обязательны Python и PostgreSQL."}'
```

`source_text` is optional. Sending `{}` or an empty string creates an approvable empty brief without
calling the model; downstream interview planning can then rely only on the vacancy and corporate
context.

The response is ready for form rendering: every populated field contains `field_key`, a Russian
`label`, `value`, `origin`, provenance, `confidence`, and `confirmation_status`. Unmentioned fields
are absent from `fields`; the UI can render them as blank using the fixed field keys and add only
values entered by the manager. Save changed fields with
`PATCH /manager/vacancies/{vacancy_id}/brief-drafts/{draft_id}` and the returned `revision`; a stale
revision returns `409` instead of overwriting another edit. Approve through
`POST .../{draft_id}/approve` with `confirm_no_automatic_rejection=true`.

```json
{
  "expected_revision": 1,
  "updates": [
    {
      "field_key": "seniority",
      "value": "middle",
      "confirmation_status": "confirmed"
    },
    {
      "field_key": "nice_to_have_competencies",
      "value": ["Kafka"],
      "confirmation_status": "rejected"
    }
  ]
}
```

Only the immutable approved version is exposed at
`GET /manager/vacancies/{vacancy_id}/approved-brief-context`. This projection omits the raw manager
text, unresolved fields, rejected proposals, and validation metadata, so it can be passed to the
separate interview-analysis agent without reinterpreting an unapproved conversation.

## Session-scoped multi-agent harness

The recruiter can now create one durable agent session for an application. It pins the vacancy,
latest resume, optional approved manager brief, scoring scale, aggregation policy, and content
hashes. The five semantic stages all use the OpenAI Responses API with purpose-specific system
instructions and strict Pydantic Structured Outputs:

1. `resume_relevance` separates explicit work positions, then maps their exact resume excerpts to
   vacancy and approved manager requirements.
2. `question_plan` preserves a fixed four-question baseline and may add bounded claim-verification
   questions.
3. `answer_assessment` evaluates one already stored completed transcript by independent technical,
   soft-skill, corporate-competency, vacancy-fit, and optional leadership criteria.
4. `alternative_vacancy_match` compares an eligible evidence profile with each active alternative.
5. `integrity_check` surfaces two-sided inconsistencies for human review and cannot create a
   restriction or blacklist.

There is deliberately no heuristic runtime fallback for these stages. Missing credentials or a
provider failure creates a retryable audited attempt. Local code validates exact evidence spans and
identity links, then deterministically calculates profile values, coverage, strong-pool eligibility,
and compatible vacancy rank. It does not make a hiring decision.

Configure the shared LLM provider and versioned deterministic policies:

```bash
OPENAI_API_KEY=...
OPENAI_BASE_URL=https://api.openai.com/v1
MULTI_AGENT_MODEL=gpt-5.4-mini
MULTI_AGENT_MAX_ATTEMPTS=3
MULTI_AGENT_TIMEOUT_SECONDS=90
STRONG_POOL_MIN_READINESS=0.25
STRONG_POOL_MIN_COVERAGE=0.50
ALTERNATIVE_VACANCY_MIN_FIT=0.25
ALTERNATIVE_MAX_GRADE_DISTANCE=1
MULTI_AGENT_PERSONALIZATION_CAP=3
```

After migration `005_multi_agent_harness`, call the recruiter endpoints in this order:

```text
POST .../applications/{invitation_id}/agent-session
POST .../agent-session/resume-analysis
POST .../agent-session/question-plan
GET  /candidate/{candidate_token}/questions
POST .../agent-session/answer-assessments
POST .../agent-session/finalize
GET  /recruiter/vacancies/{vacancy_id}/ranking
```

Every POST stage requires an `Idempotency-Key`. Answer assessment accepts a `response_id` whose
transcript status is already `completed` and whose question ID belongs to the pinned plan. Full curl
examples are in `specs/003-multi-agent-interview-flow/quickstart.md`.

Every baseline answer is returned as separate technical, soft-skill, corporate-competency, and
vacancy-fit observations. A block unsupported by that answer remains `null`; evidence from one block
is never copied into another.

Restrictions are a separate human-only audit stream:

```text
POST /recruiter/applications/{invitation_id}/restrictions
GET  /recruiter/applications/{invitation_id}/restrictions
```

An authorized recruiter supplies stored evidence references and may append `restricted`,
`blacklisted`, `verified_misrepresentation`, or a superseding `cleared` record. The operation never
rewrites LLM observations, scores, transcripts, or prior decisions.
