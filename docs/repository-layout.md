# Repository layout

The repository is organized as a small monorepo with a strict separation between runtime code,
shared packages, research, and generated artifacts.

```text
apps/
├── api/             FastAPI API, workers, migrations, scripts, and backend tests
├── candidate-web/   Candidate interview UI
└── staff-web/       Recruiter and hiring-manager cabinet
packages/
└── brand-tokens/    Shared CSS design tokens
deploy/              Container images, Compose configuration, and nginx
docs/                Current engineering and operations documentation
specs/               Feature specifications and implementation history
tools/               Development and research utilities
prototypes/          Earlier implementations that remain runnable
tests/               Tests grouped by subsystem
product-research/    Interviews, market research, and source materials
outputs/             Reports and machine-readable outputs
archive/              Retired code kept only for reference
```

## Placement rules

- Put deployable applications only in `apps/`.
- Put reusable cross-application code only in `packages/`.
- Keep runtime-generated media, databases, model weights, caches, and secrets out of Git.
- Put evaluation outputs and reports in `outputs/`, never inside an application directory.
- Keep historical feature decisions in `specs/`; use `docs/` for current operating instructions.
- Do not import from `archive/` in supported runtime code.

Historical specs may use the paths that existed when a feature was implemented. Read them with
this migration map: `backend/` → `apps/api/`, `frontend/` → `apps/candidate-web/`,
`frontend_ux/` → `apps/staff-web/`, `backend_ux/` → `archive/legacy-staff-api/`,
`interview_platform/` → `prototypes/interview-platform/interview_platform/`, and
`product_engineering/` → `tools/product-research/product_engineering/`. Current quickstarts and
deployment files use the new paths.

## Common commands

Run commands from the repository root unless a document explicitly says otherwise.

```bash
PYTHONPATH=apps/api python -m unittest discover -s apps/api/tests -v
PYTHONPATH=tools/product-research:prototypes/interview-platform python -m unittest discover -s tests -v
python -m compileall -q apps/api/app tools/product-research/product_engineering prototypes/interview-platform/interview_platform
npm test
npm run build
```
