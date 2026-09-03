# Tasks: Three-Role Interview Platform POC

**Input**: [spec.md](spec.md), [plan.md](plan.md), [data-model.md](data-model.md),
[contracts/openapi.yaml](contracts/openapi.yaml), and [quickstart.md](quickstart.md)

## Phase 1: Shared candidate foundation

- [X] T001 Keep interview lifecycle, consent, resumable answers, and synthetic-only validation in
  interview_platform/domain/models.py
- [X] T002 Keep repository and media boundaries in interview_platform/application/ports.py
- [X] T003 Keep digest-only candidate tokens and transactional interview persistence in
  interview_platform/infrastructure/sqlite_repository.py
- [X] T004 Keep the explicitly labeled text capture adapter in
  interview_platform/infrastructure/video_stub.py

## Phase 2: Separate recruiter and manager domains

- [X] T005 Add RecruiterReview, ReviewEvidence, RecruiterDecision, and ManagerReview to
  interview_platform/domain/roles.py
- [X] T006 Define role persistence ports in interview_platform/application/role_ports.py
- [X] T007 Implement recruiter funnel/review/publication/assignment and manager assigned-review
  use cases in interview_platform/application/role_services.py
- [X] T008 Persist recruiter and manager records in independent SQLite tables in
  interview_platform/infrastructure/sqlite_role_repository.py
- [X] T009 Add service/repository tests for exact evidence, publication safety, assignment,
  independent decisions, and reassignment in tests/test_interview_roles.py

## Phase 3: Three isolated delivery surfaces

- [X] T010 Add distinct recruiter and manager secrets and manager assignment id in
  interview_platform/config.py
- [X] T011 Add separate Basic Auth and API-key checks in interview_platform/web/auth.py
- [X] T012 Add role selector, recruiter funnel/review pages, assigned-manager pages, and
  candidate-safe feedback in interview_platform/web/presenters.py
- [X] T013 Add recruiter HTML/API routes and restrict invitation creation/publication to the
  recruiter in interview_platform/web/app.py
- [X] T014 Restrict manager list/detail to recruiter assignments and add the separate manager
  decision route in interview_platform/web/app.py
- [X] T015 Add responsive visual distinction for all three portals in
  interview_platform/web/static/styles.css
- [X] T016 Add authorization, non-disclosure, operation-boundary, and feedback-leak regression
  tests in tests/test_interview_web.py

## Phase 4: Composition, documentation, and validation

- [X] T017 Wire RoleService and SQLiteRoleReviewRepository into interview_platform/__main__.py
- [X] T018 Document three credentials, role flow, and validation in README.md and .env.example
- [X] T019 Align spec, plan, model, API contract, research, and quickstart in
  specs/001-interview-platform-architecture/
- [X] T020 Run the complete unittest suite, compileall, research dry run, and local smoke scenario

## Dependency order

T001–T004 are the stable candidate foundation. T005–T009 establish role invariants before HTTP.
T010–T016 expose those use cases without weakening service-level checks. T017–T020 compose and
verify the complete POC.
