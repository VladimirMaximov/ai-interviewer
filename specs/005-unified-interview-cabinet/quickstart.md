# Quickstart: Remote Demonstration Cabinet

The implementation is deployed to the existing remote stack, not to the local Docker
environment. Run commands from the repository root and keep credentials in the server
environment only.

## Deploy

```bash
ssh root@212.41.11.31
cd /opt/ai-interviewer
docker compose -f deploy/docker-compose.prototype.yml ps
docker compose -f deploy/docker-compose.prototype.yml run --rm backend alembic upgrade head
docker compose -f deploy/docker-compose.prototype.yml up -d --build
```

The migration and seed commands must be idempotent. The seed creates or updates the one
`Middle+ Python Developer` vacancy and at least ten rows with `source_kind=synthetic`; it must
not overwrite real team interviews.

## Smoke test

1. Open `https://napoleonit-career.ru/` and choose recruiter.
2. Confirm the vacancy list contains `Middle+ Python Developer`; open “Редактировать” and
   verify that the description, requirements, and manager brief are read-only.
3. Open “Результаты”; verify at least ten synthetic pseudonyms, statuses, scores, placeholder
   media, and reviewer-only antifraud timestamps.
4. Open one row and verify resume card, video, question intervals, clickable seeks, summary,
   full report, and synthetic label.
5. Create two invitations, open them in separate private windows, enter different names and
   resumes, and confirm that the sessions and leaderboard rows remain separate.

## Media validation

With a recruiter access token, verify range delivery without downloading the full object:

```bash
curl -i -H 'Range: bytes=0-1023' \
  'https://napoleonit-career.ru/api/recruiter/media/<session-id>'
```

Expected response: `206 Partial Content`, a bounded `Content-Range`, correct `Content-Length`,
and no public object URL. Test an invalid range and an absent synthetic/real asset as well.

## Completion validation

For a test invitation, enter a pseudonym and resume, grant media permissions, complete all
questions, and verify the sequence `in_progress -> processing -> completed` in the recruiter
view. If a transcription or agent job fails, the session remains visible as processing or
review-required and a retry does not duplicate assessments or report rows.

## Required checks before rollout

```bash
PYTHONPATH=apps/api python -m unittest discover -s apps/api/tests -v
python -m compileall -q apps/api/app
npm --prefix apps/candidate-web run build
npm --prefix apps/staff-web run build
```

Also inspect container logs for token values, candidate resume text, and media URLs before
declaring the remote demonstration ready.
