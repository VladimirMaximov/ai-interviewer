"""SQLite persistence adapter for vacancy-aware hiring aggregates."""

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any

from .migration_runner import apply_migrations


class SQLiteHiringRepository:
    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        self._connection = sqlite3.connect(self.path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        with self._lock:
            apply_migrations(self._connection)

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    @staticmethod
    def _json(payload: dict[str, Any]) -> str:
        return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    @staticmethod
    def _payload(row: sqlite3.Row | None) -> dict[str, Any] | None:
        return json.loads(row["payload_json"]) if row is not None else None

    def save_framework(self, payload: dict[str, Any]) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT INTO competency_frameworks (id, version, content_hash, payload_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    content_hash = excluded.content_hash,
                    payload_json = excluded.payload_json
                """,
                (
                    payload["id"],
                    payload["version"],
                    payload["content_hash"],
                    self._json(payload),
                    payload.get("created_at", "reference-data"),
                ),
            )

    def get_framework(self) -> dict[str, Any] | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT payload_json FROM competency_frameworks ORDER BY version DESC LIMIT 1"
            ).fetchone()
            return self._payload(row)

    def save_vacancy(self, payload: dict[str, Any]) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT INTO vacancies (
                    id, status, role_key, target_level_key, active_profile_version_id,
                    payload_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    status = excluded.status,
                    active_profile_version_id = excluded.active_profile_version_id,
                    payload_json = excluded.payload_json,
                    updated_at = excluded.updated_at
                """,
                (
                    payload["id"],
                    payload["status"],
                    payload["role_key"],
                    payload["target_level_key"],
                    payload.get("active_profile_version_id"),
                    self._json(payload),
                    payload["created_at"],
                    payload["updated_at"],
                ),
            )

    def get_vacancy(self, vacancy_id: str) -> dict[str, Any] | None:
        return self._one("vacancies", vacancy_id)

    def list_vacancies(self) -> list[dict[str, Any]]:
        return self._many("SELECT payload_json FROM vacancies ORDER BY updated_at DESC")

    def save_context_source(self, payload: dict[str, Any]) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT INTO vacancy_context_sources (
                    id, vacancy_id, status, content_hash, payload_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    status = excluded.status,
                    content_hash = excluded.content_hash,
                    payload_json = excluded.payload_json
                """,
                (
                    payload["id"],
                    payload["vacancy_id"],
                    payload["status"],
                    payload["content_hash"],
                    self._json(payload),
                    payload["created_at"],
                ),
            )

    def get_context_source(self, source_id: str) -> dict[str, Any] | None:
        return self._one("vacancy_context_sources", source_id)

    def list_context_sources(self, vacancy_id: str) -> list[dict[str, Any]]:
        return self._many(
            "SELECT payload_json FROM vacancy_context_sources WHERE vacancy_id = ? ORDER BY created_at",
            (vacancy_id,),
        )

    def save_profile(self, payload: dict[str, Any]) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT INTO vacancy_profile_versions (
                    id, vacancy_id, version, status, content_hash, payload_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    status = excluded.status,
                    content_hash = excluded.content_hash,
                    payload_json = excluded.payload_json
                """,
                (
                    payload["id"],
                    payload["vacancy_id"],
                    payload["version"],
                    payload["status"],
                    payload["content_hash"],
                    self._json(payload),
                    payload["created_at"],
                ),
            )

    def get_profile(self, profile_id: str) -> dict[str, Any] | None:
        return self._one("vacancy_profile_versions", profile_id)

    def list_profiles(self, vacancy_id: str) -> list[dict[str, Any]]:
        return self._many(
            "SELECT payload_json FROM vacancy_profile_versions WHERE vacancy_id = ? ORDER BY version",
            (vacancy_id,),
        )

    def save_snapshot(self, payload: dict[str, Any]) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT INTO assessment_context_snapshots (
                    id, vacancy_id, profile_version_id, context_hash, payload_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    payload["id"],
                    payload["vacancy_id"],
                    payload["profile_version_id"],
                    payload["context_hash"],
                    self._json(payload),
                    payload["created_at"],
                ),
            )

    def get_snapshot(self, snapshot_id: str) -> dict[str, Any] | None:
        return self._one("assessment_context_snapshots", snapshot_id)

    def list_snapshots(self, vacancy_id: str) -> list[dict[str, Any]]:
        return self._many(
            "SELECT payload_json FROM assessment_context_snapshots "
            "WHERE vacancy_id = ? ORDER BY created_at",
            (vacancy_id,),
        )

    def assign_interview(
        self,
        interview_id: str,
        vacancy_id: str,
        snapshot_id: str,
        created_at: str,
    ) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT INTO interview_assignments (
                    interview_id, vacancy_id, context_snapshot_id, created_at
                ) VALUES (?, ?, ?, ?)
                """,
                (interview_id, vacancy_id, snapshot_id, created_at),
            )

    def get_assignment(self, interview_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM interview_assignments WHERE interview_id = ?",
                (interview_id,),
            ).fetchone()
            return dict(row) if row else None

    def list_assignments(self, vacancy_id: str) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM interview_assignments WHERE vacancy_id = ? ORDER BY created_at",
                (vacancy_id,),
            ).fetchall()
            return [dict(row) for row in rows]

    def save_assessment_run(self, payload: dict[str, Any]) -> None:
        self._save_with_idempotency(
            "assessment_runs",
            payload,
            extra=(
                payload["interview_id"],
                payload["context_snapshot_id"],
                payload["idempotency_key"],
                payload["status"],
                payload["compatibility_key"],
            ),
            columns="interview_id, context_snapshot_id, idempotency_key, status, compatibility_key",
        )

    def get_assessment_run(self, run_id: str) -> dict[str, Any] | None:
        return self._one("assessment_runs", run_id)

    def get_assessment_by_idempotency(self, key: str) -> dict[str, Any] | None:
        return self._by_idempotency("assessment_runs", key)

    def list_assessment_runs(self, interview_id: str) -> list[dict[str, Any]]:
        return self._many(
            "SELECT payload_json FROM assessment_runs WHERE interview_id = ? ORDER BY created_at",
            (interview_id,),
        )

    def save_ranking_snapshot(self, payload: dict[str, Any], idempotency_key: str) -> None:
        prepared = {**payload, "idempotency_key": idempotency_key}
        self._save_with_idempotency(
            "ranking_snapshots",
            prepared,
            extra=(payload["vacancy_id"], idempotency_key, payload["compatibility_key"]),
            columns="vacancy_id, idempotency_key, compatibility_key",
        )

    def get_ranking_snapshot(self, snapshot_id: str) -> dict[str, Any] | None:
        return self._one("ranking_snapshots", snapshot_id)

    def list_ranking_snapshots(self, vacancy_id: str) -> list[dict[str, Any]]:
        return self._many(
            "SELECT payload_json FROM ranking_snapshots "
            "WHERE vacancy_id = ? ORDER BY created_at",
            (vacancy_id,),
        )

    def get_ranking_by_idempotency(self, key: str) -> dict[str, Any] | None:
        return self._by_idempotency("ranking_snapshots", key)

    def save_decision(self, payload: dict[str, Any], idempotency_key: str) -> None:
        prepared = {**payload, "idempotency_key": idempotency_key}
        self._save_with_idempotency(
            "human_decisions",
            prepared,
            extra=(payload["interview_id"], payload["actor_role"], idempotency_key),
            columns="interview_id, actor_role, idempotency_key",
        )

    def get_decision_by_idempotency(self, key: str) -> dict[str, Any] | None:
        return self._by_idempotency("human_decisions", key)

    def list_decisions(self, interview_id: str) -> list[dict[str, Any]]:
        return self._many(
            "SELECT payload_json FROM human_decisions WHERE interview_id = ? ORDER BY created_at",
            (interview_id,),
        )

    def save_feedback_entry(self, payload: dict[str, Any]) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT INTO feedback_entries (
                    id, interview_id, stage, sequence, payload_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET payload_json = excluded.payload_json
                """,
                (
                    payload["id"],
                    payload["interview_id"],
                    payload["stage"],
                    payload["sequence"],
                    self._json(payload),
                    payload["created_at"],
                ),
            )

    def get_feedback_entry(self, entry_id: str) -> dict[str, Any] | None:
        return self._one("feedback_entries", entry_id)

    def list_feedback_entries(self, interview_id: str) -> list[dict[str, Any]]:
        return self._many(
            "SELECT payload_json FROM feedback_entries WHERE interview_id = ? ORDER BY sequence",
            (interview_id,),
        )

    def get_idempotent_result(self, key: str, scope: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT payload_json FROM operation_idempotency "
                "WHERE idempotency_key = ? AND operation_scope = ?",
                (key, scope),
            ).fetchone()
            return self._payload(row)

    def save_idempotent_result(
        self, key: str, scope: str, payload: dict[str, Any]
    ) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                "INSERT OR IGNORE INTO operation_idempotency "
                "(idempotency_key, operation_scope, payload_json) VALUES (?, ?, ?)",
                (key, scope, self._json(payload)),
            )

    def _one(self, table: str, object_id: str) -> dict[str, Any] | None:
        allowed = {
            "vacancies",
            "vacancy_context_sources",
            "vacancy_profile_versions",
            "assessment_context_snapshots",
            "assessment_runs",
            "ranking_snapshots",
            "feedback_entries",
        }
        if table not in allowed:
            raise ValueError("invalid table")
        with self._lock:
            row = self._connection.execute(
                f"SELECT payload_json FROM {table} WHERE id = ?",  # nosec: allowlisted table
                (object_id,),
            ).fetchone()
            return self._payload(row)

    def _many(self, query: str, parameters: tuple = ()) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._connection.execute(query, parameters).fetchall()
            return [json.loads(row["payload_json"]) for row in rows]

    def _by_idempotency(self, table: str, key: str) -> dict[str, Any] | None:
        if table not in {"assessment_runs", "ranking_snapshots", "human_decisions"}:
            raise ValueError("invalid table")
        with self._lock:
            row = self._connection.execute(
                f"SELECT payload_json FROM {table} WHERE idempotency_key = ?",  # nosec: allowlisted table
                (key,),
            ).fetchone()
            return self._payload(row)

    def _save_with_idempotency(
        self,
        table: str,
        payload: dict[str, Any],
        *,
        extra: tuple,
        columns: str,
    ) -> None:
        if table not in {"assessment_runs", "ranking_snapshots", "human_decisions"}:
            raise ValueError("invalid table")
        placeholders = ", ".join("?" for _ in extra)
        with self._lock, self._connection:
            self._connection.execute(
                f"INSERT INTO {table} (id, {columns}, payload_json, created_at) "
                f"VALUES (?, {placeholders}, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET payload_json = excluded.payload_json",  # nosec
                (
                    payload["id"],
                    *extra,
                    self._json(payload),
                    payload["created_at"],
                ),
            )
