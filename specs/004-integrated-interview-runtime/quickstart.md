# Quickstart: Integrated Interview Runtime Validation

## Preconditions

- Use only synthetic vacancy and candidate data.
- PostgreSQL, MinIO, Redis, API, CPU worker, GPU presenter worker, candidate UI, and cabinet UI are healthy.
- NVIDIA runtime reports the Tesla T4 and the presenter worker has loaded XTTS and MuseTalk.

## Automated gates

```bash
PYTHONPATH=tools/product-research:prototypes/interview-platform python -m unittest discover -s tests -v
python -m compileall -q tools/product-research/product_engineering
PYTHONPATH=apps/api python -m unittest discover -s apps/api/tests -v
npm --prefix apps/candidate-web run test
npm --prefix apps/candidate-web run build
npm --prefix apps/staff-web run test -- --watchAll=false
npm --prefix apps/staff-web run build
```

Expected: all commands pass; no synthetic media or database files appear in `git status`.

## Synthetic E2E scenario

1. Open the cabinet and create a synthetic vacancy.
2. Configure three blocks with three questions each: two spoken plus one Python coding question in hard skills, and three spoken questions in each other block.
3. Include a Russian prompt containing `PostgreSQL`, `FastAPI`, and `CI/CD`; enable follow-ups on one question and set two time limits.
4. Create an invitation and copy its candidate URL.
5. Open it in a clean browser profile. Confirm the preparation screen shows three blocks, nine questions, time-limit and coding guidance without question one.
6. Grant camera/microphone once, start, and verify question one appears and speaks exactly once.
7. Complete spoken and coding questions while confirming continuous capture and ten-second uploads.
8. Exercise a runtime follow-up fixture. If avatar rendering is forced to fail, verify audio plus static portrait and uninterrupted answering.
9. Complete the interview and verify the recruiter-contact completion screen.
10. Open the session in the cabinet and compare each question, transcript, code snapshot, follow-up, timestamp, and recording status with backend records.

## Runtime acceptance measurements

- Warmed presenter is ready within 2 seconds.
- Dynamic follow-up starts within 15 seconds in 9 of 10 trials.
- Four of five reviewers understand mixed-language technical terms without seeing text.
- GPU queue concurrency remains one and API health stays responsive.
- Restarting a worker leaves work retryable rather than lost.

## Failure validation

- Invalid, expired, and completed invitations return terminal messages.
- Duplicate invitation or presenter requests do not duplicate assets.
- Malformed three-block input receives field-specific errors.
- Pending/failed processing is explicit and never replaced by mock content.
- No automated candidate rejection occurs.
