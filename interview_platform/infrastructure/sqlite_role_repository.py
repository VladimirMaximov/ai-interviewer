"""SQLite persistence for recruiter assignments and separate human reviews."""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path

from interview_platform.domain.models import EvidenceKind, ManagerDecision, PublicationStatus
from interview_platform.domain.roles import (
    ManagerReview,
    RecruiterDecision,
    RecruiterReview,
    ReviewEvidence,
)


ROLE_SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS recruiter_reviews (
    id TEXT PRIMARY KEY,
    interview_id TEXT NOT NULL UNIQUE REFERENCES interviews(id) ON DELETE CASCADE,
    candidate_summary TEXT NOT NULL,
    strengths_json TEXT NOT NULL,
    risks_json TEXT NOT NULL,
    next_steps TEXT NOT NULL,
    internal_notes TEXT NOT NULL,
    recruiter_decision TEXT NOT NULL,
    assigned_manager TEXT,
    publication_status TEXT NOT NULL,
    version INTEGER NOT NULL,
    published_at TEXT,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS recruiter_review_evidence (
    id TEXT PRIMARY KEY,
    review_id TEXT NOT NULL REFERENCES recruiter_reviews(id) ON DELETE CASCADE,
    kind TEXT NOT NULL,
    question_id TEXT NOT NULL REFERENCES questions(id),
    excerpt TEXT,
    note TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS manager_reviews (
    id TEXT PRIMARY KEY,
    interview_id TEXT NOT NULL UNIQUE REFERENCES interviews(id) ON DELETE CASCADE,
    manager_id TEXT NOT NULL,
    manager_decision TEXT NOT NULL,
    notes TEXT NOT NULL,
    reviewed_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_recruiter_reviews_manager
ON recruiter_reviews(assigned_manager, updated_at);
"""


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _datetime(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value is not None else None


class SQLiteRoleReviewRepository:
    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        self._connection = sqlite3.connect(self.path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        with self._lock, self._connection:
            self._connection.executescript(ROLE_SCHEMA)
            self._connection.execute("PRAGMA optimize")

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def get_recruiter_review(self, interview_id: str) -> RecruiterReview | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM recruiter_reviews WHERE interview_id = ?",
                (interview_id,),
            ).fetchone()
            if row is None:
                return None
            evidence_rows = self._connection.execute(
                "SELECT * FROM recruiter_review_evidence WHERE review_id = ? ORDER BY rowid",
                (row["id"],),
            ).fetchall()
            return RecruiterReview(
                id=row["id"],
                interview_id=row["interview_id"],
                candidate_summary=row["candidate_summary"],
                strengths=tuple(json.loads(row["strengths_json"])),
                risks=tuple(json.loads(row["risks_json"])),
                next_steps=row["next_steps"],
                internal_notes=row["internal_notes"],
                recruiter_decision=RecruiterDecision(row["recruiter_decision"]),
                assigned_manager=row["assigned_manager"],
                publication_status=PublicationStatus(row["publication_status"]),
                evidence=tuple(
                    ReviewEvidence(
                        id=item["id"],
                        review_id=item["review_id"],
                        kind=EvidenceKind(item["kind"]),
                        question_id=item["question_id"],
                        excerpt=item["excerpt"],
                        note=item["note"],
                    )
                    for item in evidence_rows
                ),
                version=row["version"],
                published_at=_datetime(row["published_at"]),
                updated_at=_datetime(row["updated_at"]),
            )

    def save_recruiter_review(self, review: RecruiterReview) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT INTO recruiter_reviews (
                    id, interview_id, candidate_summary, strengths_json, risks_json,
                    next_steps, internal_notes, recruiter_decision, assigned_manager,
                    publication_status, version, published_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(interview_id) DO UPDATE SET
                    candidate_summary = excluded.candidate_summary,
                    strengths_json = excluded.strengths_json,
                    risks_json = excluded.risks_json,
                    next_steps = excluded.next_steps,
                    internal_notes = excluded.internal_notes,
                    recruiter_decision = excluded.recruiter_decision,
                    assigned_manager = excluded.assigned_manager,
                    publication_status = excluded.publication_status,
                    version = excluded.version,
                    published_at = excluded.published_at,
                    updated_at = excluded.updated_at
                """,
                (
                    review.id,
                    review.interview_id,
                    review.candidate_summary,
                    json.dumps(review.strengths, ensure_ascii=False),
                    json.dumps(review.risks, ensure_ascii=False),
                    review.next_steps,
                    review.internal_notes,
                    review.recruiter_decision.value,
                    review.assigned_manager,
                    review.publication_status.value,
                    review.version,
                    _iso(review.published_at),
                    _iso(review.updated_at),
                ),
            )
            self._connection.execute(
                "DELETE FROM recruiter_review_evidence WHERE review_id = ?",
                (review.id,),
            )
            self._connection.executemany(
                """
                INSERT INTO recruiter_review_evidence (
                    id, review_id, kind, question_id, excerpt, note
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        item.id,
                        item.review_id,
                        item.kind.value,
                        item.question_id,
                        item.excerpt,
                        item.note,
                    )
                    for item in review.evidence
                ],
            )

    def assigned_interview_ids(self, manager_id: str) -> list[str]:
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT interview_id FROM recruiter_reviews
                WHERE assigned_manager = ? ORDER BY updated_at DESC
                """,
                (manager_id,),
            ).fetchall()
            return [row["interview_id"] for row in rows]

    def get_manager_review(self, interview_id: str) -> ManagerReview | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM manager_reviews WHERE interview_id = ?",
                (interview_id,),
            ).fetchone()
            if row is None:
                return None
            return ManagerReview(
                id=row["id"],
                interview_id=row["interview_id"],
                manager_id=row["manager_id"],
                manager_decision=ManagerDecision(row["manager_decision"]),
                notes=row["notes"],
                reviewed_at=_datetime(row["reviewed_at"]),
            )

    def save_manager_review(self, review: ManagerReview) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT INTO manager_reviews (
                    id, interview_id, manager_id, manager_decision, notes, reviewed_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(interview_id) DO UPDATE SET
                    id = excluded.id,
                    manager_id = excluded.manager_id,
                    manager_decision = excluded.manager_decision,
                    notes = excluded.notes,
                    reviewed_at = excluded.reviewed_at
                """,
                (
                    review.id,
                    review.interview_id,
                    review.manager_id,
                    review.manager_decision.value,
                    review.notes,
                    _iso(review.reviewed_at),
                ),
            )

    def clear_manager_review(self, interview_id: str) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                "DELETE FROM manager_reviews WHERE interview_id = ?",
                (interview_id,),
            )
