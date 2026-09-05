# Integrated runtime validation — 2026-09-05

Only synthetic fixtures were used.

## Passed locally

- Product pipeline: 79 unit tests passed.
- Main backend: 121 unit/integration tests passed.
- Candidate UI: 18 tests passed; TypeScript and Vite production build passed.
- Cabinet UI: 4 tests passed; TypeScript and CRA production build passed.
- Python compile gates passed for `product_engineering` and `backend/app`.
- Docker Compose configuration parses successfully.
- Clean Docker builds passed for API, candidate UI, and cabinet UI.
- PostgreSQL, MinIO initialization, Redis, API, both UIs, and Nginx gateway started locally.
- HTTP smoke tests returned 200 for `/api/health`, `/api/ready`, `/`, and `/interview/`.
- Readiness confirmed PostgreSQL, private object storage, and Redis. GPU presenter checks were intentionally disabled on the Mac host.

Two container defects were found and corrected during the smoke test: the Redis client pin was incompatible with Kombu, and Alembic ignored the container `DATABASE_URL`. The UI containers also received an explicit Nginx document root.

## Pending T4 acceptance

The Tesla T4 host still needs the prepared MuseTalk checkout, model weights, and presenter portrait mounted through `MUSETALK_ROOT` and `PRESENTER_MODELS_PATH`. The final gate must then exercise a mixed Russian/English question, a runtime follow-up, forced avatar failure, worker restart/retry, and the 10-trial latency measurements from the feature quickstart. Task T050 remains open until those measurements are collected.

## Repository audit

No newly added recording, transcript, model weight, credential, `.env`, generated WAV, or generated MP4 is present in the change set. The pre-existing `backend_ux/interview.db` was removed from Git tracking without deleting the developer's local file; `*.db` remains ignored.
