# Implementation Plan: Three-Role Interview Platform POC

**Branch**: main | **Date**: 2026-09-03 | **Spec**: [spec.md](spec.md)

## Summary

Deliver a runnable architecture-first POC with three isolated surfaces:

- candidate: token-scoped interview completion and published feedback;
- recruiter: full funnel, invitation creation, evidence-first review, publication, and assignment;
- manager: assigned candidates only and an independent hiring review.

Real video, transcription, automated evaluation, notifications, SSO, and ATS integration remain
outside this slice. The capture port is represented by an explicitly labeled text stub.

## Technical context

- Python 3.12+, standard library only
- modular monolith and WSGI delivery adapter
- SQLite repositories with explicit schema bootstrap
- unittest coverage for domain, persistence, services, HTTP, and authorization
- local macOS/Linux target; production identity and deployment deferred
- synthetic demo data only; no recordings, transcripts, candidate PII, or secrets committed

## Architecture

~~~text
candidate / recruiter / manager HTML + JSON
                    |
                    v
web: routing, role authentication, safe projections
                    |
                    v
application: InterviewService + RoleService + ports
                    |
                    v
domain: interview state + RecruiterReview + ManagerReview + evidence
                    ^
                    |
infrastructure: SQLite interview/role repositories + text capture stub
~~~

Dependencies point inward. Role authorization is enforced in RoleService as well as routing:
manager lookup requires a matching recruiter assignment, and candidate feedback is projected from a
published recruiter review only.

## Project changes

~~~text
interview_platform/
├── config.py
├── domain/
│   ├── models.py
│   └── roles.py
├── application/
│   ├── ports.py
│   ├── role_ports.py
│   ├── services.py
│   └── role_services.py
├── infrastructure/
│   ├── sqlite_repository.py
│   ├── sqlite_role_repository.py
│   └── video_stub.py
└── web/
    ├── auth.py
    ├── app.py
    ├── presenters.py
    └── static/styles.css

tests/
├── test_interview_roles.py
└── test_interview_web.py
~~~

## Design decisions

1. Keep Interview and the new role reviews in separate domain records so existing interview state
   and future assessment modules remain stable.
2. Store recruiter review, evidence, assignment, and manager review in dedicated SQLite tables.
3. Use different Basic Auth usernames/secrets and different API headers for recruiter and manager.
4. Return not found for an unassigned manager lookup to avoid disclosing candidate existence.
5. Return a raw invitation token only from recruiter creation; store and later expose no raw token.
6. Treat assignment as authorization data. Reassignment revokes old access and clears the stale
   current manager review.
7. Keep ai_recommendation empty and never derive an automatic hiring decision.

## Constitution and repository checks

- Standard-library alignment: PASS.
- Evidence-first evaluation: PASS; exact stored excerpts or insufficient_information are required.
- Separated decisions: PASS; recruiter and manager use distinct entities/tables.
- No automatic rejection or biometric scoring: PASS.
- Privacy: PASS; token digests and synthetic-only committed data.
- Regression coverage: PASS; success, invalid evidence, unauthorized, unassigned, draft/publication,
  reassignment, persistence, and whole-repository tests are included.

No constitution exception or new external dependency is required.
