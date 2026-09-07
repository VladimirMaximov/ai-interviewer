PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS competency_frameworks (
    id TEXT PRIMARY KEY,
    version INTEGER NOT NULL UNIQUE,
    content_hash TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS vacancies (
    id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    role_key TEXT NOT NULL,
    target_level_key TEXT NOT NULL,
    active_profile_version_id TEXT,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS vacancy_context_sources (
    id TEXT PRIMARY KEY,
    vacancy_id TEXT NOT NULL REFERENCES vacancies(id),
    status TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_vacancy_sources_vacancy
    ON vacancy_context_sources(vacancy_id, created_at);

CREATE TABLE IF NOT EXISTS vacancy_profile_versions (
    id TEXT PRIMARY KEY,
    vacancy_id TEXT NOT NULL REFERENCES vacancies(id),
    version INTEGER NOT NULL,
    status TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (vacancy_id, version)
);

CREATE INDEX IF NOT EXISTS idx_profile_versions_vacancy
    ON vacancy_profile_versions(vacancy_id, version);

CREATE TABLE IF NOT EXISTS assessment_context_snapshots (
    id TEXT PRIMARY KEY,
    vacancy_id TEXT NOT NULL REFERENCES vacancies(id),
    profile_version_id TEXT NOT NULL REFERENCES vacancy_profile_versions(id),
    context_hash TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS interview_assignments (
    interview_id TEXT PRIMARY KEY,
    vacancy_id TEXT NOT NULL REFERENCES vacancies(id),
    context_snapshot_id TEXT NOT NULL REFERENCES assessment_context_snapshots(id),
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_assignments_vacancy
    ON interview_assignments(vacancy_id, created_at);

CREATE TABLE IF NOT EXISTS assessment_runs (
    id TEXT PRIMARY KEY,
    interview_id TEXT NOT NULL,
    context_snapshot_id TEXT NOT NULL REFERENCES assessment_context_snapshots(id),
    idempotency_key TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL,
    compatibility_key TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_assessment_runs_interview
    ON assessment_runs(interview_id, created_at);

CREATE TABLE IF NOT EXISTS ranking_snapshots (
    id TEXT PRIMARY KEY,
    vacancy_id TEXT NOT NULL REFERENCES vacancies(id),
    idempotency_key TEXT NOT NULL UNIQUE,
    compatibility_key TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_rankings_vacancy
    ON ranking_snapshots(vacancy_id, created_at);

CREATE TABLE IF NOT EXISTS human_decisions (
    id TEXT PRIMARY KEY,
    interview_id TEXT NOT NULL,
    actor_role TEXT NOT NULL,
    idempotency_key TEXT NOT NULL UNIQUE,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_decisions_interview
    ON human_decisions(interview_id, created_at);

CREATE TABLE IF NOT EXISTS feedback_entries (
    id TEXT PRIMARY KEY,
    interview_id TEXT NOT NULL,
    stage TEXT NOT NULL,
    sequence INTEGER NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (interview_id, sequence)
);

CREATE INDEX IF NOT EXISTS idx_feedback_entries_interview
    ON feedback_entries(interview_id, sequence);

CREATE TABLE IF NOT EXISTS audit_events (
    id TEXT PRIMARY KEY,
    actor_id TEXT NOT NULL,
    action TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
