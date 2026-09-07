CREATE TABLE IF NOT EXISTS operation_idempotency (
    idempotency_key TEXT NOT NULL,
    operation_scope TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (idempotency_key, operation_scope)
);
