# Validation Guide

1. Apply migrations: `PYTHONPATH=apps/api python -m alembic -c apps/api/alembic.ini upgrade head`.
2. Create an invitation from `interview-input.example.json`, containing spoken and coding blocks.
3. Save an eligible spoken answer; verify the next base question does not wait and one stub job
   completes with zero prompts.
4. Save a coding question; verify text and language persist and no code runs.
5. Inject a valid two-prompt decision; verify both prompts append after base questions.

## Validation recorded 2026-09-04

- `PYTHONPATH=apps/api python -m unittest discover -s apps/api/tests -v` — 53 tests passed.
- `PYTHONPATH=apps/api python -m compileall -q apps/api/app` — passed.
- `npm --prefix apps/candidate-web run build` — passed.
- `alembic upgrade head` against the local PostgreSQL instance — passed; head is `011_code_answers`.
