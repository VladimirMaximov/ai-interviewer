# Quickstart: Three-Role Interview Platform POC

## Start a local demo

Requires Python 3.12 or newer and no third-party packages.

~~~bash
export INTERVIEW_RECRUITER_KEY='local-recruiter-secret'
export INTERVIEW_MANAGER_KEY='local-manager-secret'
python -m interview_platform \
  --db-path /tmp/interview-platform-three-roles.sqlite3 \
  --seed-demo
~~~

The secrets must differ and contain at least eight characters. Open
http://127.0.0.1:8000/ to see the role selector.

| Role | URL | Browser credentials |
|---|---|---|
| Candidate | URL printed as “Synthetic candidate” | Personal link, no Basic Auth |
| Recruiter | http://127.0.0.1:8000/recruiter | user “recruiter”, recruiter environment secret |
| Manager | http://127.0.0.1:8000/manager | user “manager”, manager environment secret |

Use separate private browser windows for recruiter and manager so cached Basic Auth credentials do
not obscure the role boundary. The seeded alias is synthetic.

## Verify the complete flow

1. Open the printed candidate link, accept consent, answer every question, and submit.
2. Open /recruiter. The recruiter sees the whole funnel and the submitted candidate.
3. Open the candidate card. Enter feedback and an exact excerpt copied from one answer.
4. Keep the prefilled assignment “hiring-manager”, choose a recruiter decision, and first save a
   draft. The candidate must still see “Проверка продолжается”.
5. Publish the recruiter review. The candidate now sees only the summary, strengths, and next
   steps—not risks, internal notes, assignment, evidence, or hiring decisions.
6. Open /manager. The candidate now appears because the recruiter assigned it.
7. Open the card and save the manager's own decision. Return to the recruiter card and confirm the
   recruiter and manager decisions remain separate.

Before assignment, /manager is intentionally empty. A direct manager request for an unassigned
interview returns 404, and the manager cannot create invitations or publish candidate feedback.

## Verify the API boundary

~~~bash
curl -sS http://127.0.0.1:8000/health
curl -sS -H 'X-Recruiter-Key: local-recruiter-secret' \
  http://127.0.0.1:8000/api/recruiter/interviews
curl -sS -H 'X-Manager-Key: local-manager-secret' \
  http://127.0.0.1:8000/api/manager/interviews
~~~

The recruiter collection contains the full funnel. The manager collection contains only assigned
interviews. Neither collection exposes invitation tokens; a raw token is returned only once when a
recruiter creates an invitation.

## Run automated validation

~~~bash
python -m unittest discover -s tests -v
python -m compileall -q product_engineering interview_platform
python -m product_engineering "AI technical interview" --dry-run
~~~

All commands must exit with code 0. Tests use temporary databases and synthetic aliases only.
