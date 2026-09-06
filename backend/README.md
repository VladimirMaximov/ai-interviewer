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

GigaAM v3 (`v3_e2e_rnnt`) is available in long-form mode. It uses the model's VAD integration to
split arbitrary-length Russian recordings into short speech segments and joins their text. Set
`TRANSCRIPTION_PROVIDER=gigaam3` and provide an `HF_TOKEN` after accepting access conditions for
`pyannote/segmentation-3.0`. The model itself remains local; the token is used only to download
the VAD model. RouterAI remains an optional external benchmark adapter.

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
hashes. The six semantic stages all use the OpenAI Responses API with purpose-specific system
instructions and strict Pydantic Structured Outputs:

1. `resume_relevance` separates explicit work positions, then maps immutable resume evidence IDs to
   vacancy and approved-manager requirement IDs.
2. `question_plan` preserves a fixed four-question baseline and may add bounded claim-verification
   questions.
3. `answer_assessment` evaluates one already stored completed transcript by independent technical,
   soft-skill, corporate-competency, vacancy-fit, and optional leadership criteria.
4. `alternative_vacancy_match` compares an eligible evidence profile with each active alternative.
5. `integrity_check` surfaces two-sided inconsistencies for human review and cannot create a
   restriction or blacklist.
6. `candidate_feedback` turns the finalized profile, stored answers, answer assessments, resume
   relevance, and already eligible alternatives into an evidence-linked Russian draft for the
   candidate.

There is deliberately no heuristic runtime fallback for these stages. Missing credentials or a
provider failure creates a retryable audited attempt. Local code builds stable source-owned evidence
catalogs, validates the IDs selected by each model, and resolves their verbatim text only in a
separate view. Raw JSON outputs—including schema-invalid attempts—are not repaired or normalized.
Profile values, coverage, strong-pool eligibility, and compatible vacancy rank are calculated
deterministically and separately. The system does not make a hiring decision.

Configure the shared LLM provider and versioned deterministic policies:

```bash
OPENAI_API_KEY=...
OPENAI_BASE_URL=https://api.openai.com/v1
MULTI_AGENT_MODEL=gpt-5.4-mini
MULTI_AGENT_API_MODE=responses
MULTI_AGENT_MAX_ATTEMPTS=3
MULTI_AGENT_TIMEOUT_SECONDS=90
STRONG_POOL_MIN_READINESS=0.25
STRONG_POOL_MIN_COVERAGE=0.50
ALTERNATIVE_VACANCY_MIN_FIT=0.25
ALTERNATIVE_MAX_GRADE_DISTANCE=1
MULTI_AGENT_PERSONALIZATION_CAP=3
FOLLOW_UP_CONFIDENCE_THRESHOLD=0.65
FOLLOW_UP_MAX_PER_SESSION=2
```

For an OpenAI-compatible provider that exposes Chat Completions, such as VseGPT, use its
provider-prefixed model ID together with `MULTI_AGENT_API_MODE=chat_completions`.

After migrations `005_multi_agent_harness` and `006_candidate_feedback_agent`, call the recruiter
endpoints in this order:

```text
POST .../applications/{invitation_id}/agent-session
POST .../agent-session/resume-analysis
POST .../agent-session/question-plan
GET  /candidate/{candidate_token}/questions
POST /candidate/{candidate_token}/live-coding-responses
POST .../agent-session/answer-assessments
POST .../agent-session/finalize
POST .../agent-session/candidate-feedback
POST .../agent-session/candidate-feedback/{release_id}/publish
GET  /candidate/{candidate_token}/feedback
GET  /recruiter/vacancies/{vacancy_id}/ranking
```

Every POST stage requires an `Idempotency-Key`. Answer assessment accepts a `response_id` whose
transcript status is already `completed` and whose question ID belongs to the pinned plan. Full curl
examples are in `specs/003-multi-agent-interview-flow/quickstart.md`.

Every baseline answer is returned as separate technical, soft-skill, corporate-competency, and
vacancy-fit observations. A block unsupported by that answer remains `null`; evidence from one block
is never copied into another.

If a candidate cannot demonstrate a technical skill explicitly claimed in the resume and linked to
the vacancy requirement, the assessor may add one practical `live_coding` task. The candidate UI
opens a code editor automatically. Exactly one solution is stored as a completed text response,
assessed through the same evidence-first stage, and included in the technical score. The session can
never expose a second live-coding section and cannot be finalized before that solution is assessed.

Candidate feedback is never published directly by the model. The generation endpoint creates an
immutable `draft`; an authenticated recruiter reviews it and calls the publication endpoint. Until
then, the candidate receives `pending_review`. The published projection contains the deterministic
0–10 interview score, strengths, actionable growth areas, experience alignment, next steps, and at
most one currently active alternative vacancy. It omits rank, pool membership, integrity and
restriction data, model confidence, and internal evidence identifiers. The frontend reads this
projection from the same bearer invitation link when the candidate returns.

Restrictions are a separate human-only audit stream:

```text
POST /recruiter/applications/{invitation_id}/restrictions
GET  /recruiter/applications/{invitation_id}/restrictions
```

An authorized recruiter supplies stored evidence references and may append `restricted`,
`blacklisted`, `verified_misrepresentation`, or a superseding `cleared` record. The operation never
rewrites LLM observations, scores, transcripts, or prior decisions.

## Camera presence and speaker monitoring

During each answer, the candidate frontend requests camera and microphone access. The official
[MediaPipe Face Detector](https://ai.google.dev/edge/mediapipe/solutions/vision/face_detector/web_js)
runs in the browser about three times per second. A condition must remain visible for 750
ms before an event opens, which avoids recording one missed frame as an incident. A
`face_missing` or `multiple_faces` interval starts five seconds before the first anomalous frame
and ends when exactly one face is visible again. The timestamp includes the five-second pre-roll;
video evidence begins when the condition is confirmed and is capped at 15 seconds. The API rejects
evidence over 2 MB, and the application does not upload continuous interview video.

If the browser cannot initialize the detector or cannot process a frame, the whole answer receives
a `face_detection_unavailable` interval. This is missing evidence rather than an integrity finding,
and prevents that answer from silently becoming part of the provisional voice reference.

Camera events are stored before the audio upload is confirmed. The voice worker can therefore
exclude those intervals while building a provisional reference from the first two confirmed
answers. It stores only the reference response IDs and readiness state, not a separate biometric
embedding. The third and later answers produce reviewer-only `overlapping_speech`,
`additional_speaker`, and `speaker_mismatch` intervals. The first two answers can already produce
overlap/additional-speaker intervals, but cannot produce an identity mismatch before the profile is
ready. Every signal defaults to `pending` human review and has no automatic rejection path.

The normal backend install keeps heavyweight speaker models disabled. To run local speaker
analysis, accept the access conditions for the selected Hugging Face models, install the optional
dependencies, migrate the database, and enable the provider:

- [pyannote.audio](https://github.com/pyannote/pyannote-audio) supplies diarization and
  overlapping-speech intervals.
- [SpeechBrain ECAPA-TDNN](https://speechbrain.readthedocs.io/en/stable/API/speechbrain.lobes.models.ECAPA_TDNN.html)
  supplies speaker embeddings used only during processing.

```bash
pip install -e './backend[proctoring]'
PYTHONPATH=backend alembic -c backend/alembic.ini upgrade head
export PROCTORING_PROVIDER=pyannote
export HUGGINGFACE_TOKEN=replace-with-a-read-token
```

The default similarity values are development assumptions, not validated facts. Calibrate them on
consented, representative Russian recordings and supported microphones before production use:

```text
PROCTORING_MINIMUM_REFERENCE_SECONDS=20
PROCTORING_REFERENCE_SIMILARITY=0.65
PROCTORING_SPEAKER_SIMILARITY=0.55
```

The browser defaults to official hosted MediaPipe WASM and face-detector model assets. Production
deployments should self-host pinned copies and set `VITE_MEDIAPIPE_WASM_URL` and
`VITE_FACE_DETECTOR_MODEL_URL` in `frontend/.env.local` so monitoring does not depend on a public
CDN at interview time.
