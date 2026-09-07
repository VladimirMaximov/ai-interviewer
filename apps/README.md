# Applications

Runtime applications live together in this directory:

- `api/` — FastAPI API, workers, migrations, scripts, and backend tests;
- `candidate-web/` — candidate interview UI built with React and Vite;
- `staff-web/` — recruiter and hiring-manager cabinet built with React.

Shared UI primitives belong in `../packages/`. Deployment configuration belongs in `../deploy/`.
Product research, specifications, and generated deliverables stay at the repository root and are
not runtime dependencies.
