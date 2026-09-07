# Repository Guidelines

## Project Structure & Purpose

This repository supports the Napoleon IT asynchronous technical-interview MVP and its product
research pipeline. `tools/product-research/product_engineering/` contains the standard-library
Python CLI, API client, schemas, prompts, persistence, and report generation. Keep matching unit
tests in `tests/research_pipeline/` using `test_<module>.py`. Store competitor evidence in
`product-research/market-research/` as descriptive Markdown files such as
`xenia-ai-competitor-analysis.md`. Product decisions and machine-readable outputs belong in
`outputs/ai-technical-interview/`; raw or summarized stakeholder notes belong in
`product-research/interviews/`.

## Build, Test, and Development Commands

Use Python 3.12 or newer.

```bash
PYTHONPATH=tools/product-research:prototypes/interview-platform python -m product_engineering "AI technical interview" --dry-run
PYTHONPATH=tools/product-research:prototypes/interview-platform python -m unittest discover -s tests -v
python -m compileall -q tools/product-research/product_engineering prototypes/interview-platform/interview_platform
```

The dry run validates pipeline planning without API calls. Unit tests cover transformations,
schema rules, storage, scraping, and API behavior. `compileall` catches syntax errors. For a real
run, copy `.env.example`, set `OPENAI_API_KEY` in the environment, and never commit the key.

## Coding Style & Naming Conventions

Follow PEP 8 with four-space indentation, type hints for public functions, and small modules with
single responsibilities. Use `snake_case` for functions and variables, `PascalCase` for classes,
and uppercase names for constants. Prefer deterministic code for scoring and ranking; do not ask
an LLM to calculate Pain or RICE scores. Name research files with lowercase kebab-case and keep
JSON field names in `snake_case`.

## Domain and Evidence Rules

Separate verified facts, vendor claims, external observations, and assumptions. Cite current
official sources and preserve URLs. Label simulated interviews as `synthetic`; they are not
customer validation. Candidate evaluation must be evidence-first: connect scores to transcript
quotes or timestamps, represent missing evidence explicitly, and keep AI, recruiter, and hiring
manager decisions separate. Never implement automatic rejection or score appearance, accent,
emotion, or voice confidence. Do not commit candidate PII, recordings, transcripts, or secrets.

## Testing Guidelines

Add regression tests for every parsing, schema, checkpoint, or scoring change. Test success,
malformed input, retry, and resume paths. Run the full test and compile commands before review.

## Commit & Pull Request Guidelines

No Git history is available in this workspace. Use short imperative commits with prefixes such
as `feat:`, `fix:`, `test:`, or `docs:`. Pull requests should explain the affected interview
stage, list validation commands, link source evidence, and include screenshots for candidate or
reviewer UI changes. Call out schema migrations, model changes, privacy impact, and known
evaluation gaps.
