"""SQLite adapter for the interview aggregate."""

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path

from interview_platform.domain.models import (
    Answer,
    Evidence,
    EvidenceKind,
    Feedback,
    Interview,
    InterviewStatus,
    ManagerDecision,
    PublicationStatus,
    Question,
)


SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS interviews (
    id TEXT PRIMARY KEY,
    candidate_alias TEXT NOT NULL,
    position_title TEXT NOT NULL,
    invitation_token_digest TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL,
    evidence_type TEXT NOT NULL CHECK (evidence_type = 'synthetic'),
    consent_given_at TEXT,
    started_at TEXT,
    submitted_at TEXT,
    reviewed_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS questions (
    id TEXT PRIMARY KEY,
    interview_id TEXT NOT NULL REFERENCES interviews(id) ON DELETE CASCADE,
    prompt TEXT NOT NULL,
    position INTEGER NOT NULL,
    required INTEGER NOT NULL,
    UNIQUE (interview_id, position)
);

CREATE TABLE IF NOT EXISTS answers (
    question_id TEXT PRIMARY KEY REFERENCES questions(id) ON DELETE CASCADE,
    interview_id TEXT NOT NULL REFERENCES interviews(id) ON DELETE CASCADE,
    capture_kind TEXT NOT NULL,
    content TEXT NOT NULL,
    media_reference TEXT,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS feedback (
    id TEXT PRIMARY KEY,
    interview_id TEXT NOT NULL UNIQUE REFERENCES interviews(id) ON DELETE CASCADE,
    candidate_summary TEXT NOT NULL,
    strengths_json TEXT NOT NULL,
    risks_json TEXT NOT NULL,
    next_steps TEXT NOT NULL,
    internal_notes TEXT NOT NULL,
    ai_recommendation TEXT,
    recruiter_decision TEXT,
    manager_decision TEXT NOT NULL,
    publication_status TEXT NOT NULL,
    version INTEGER NOT NULL,
    published_at TEXT,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS evidence (
    id TEXT PRIMARY KEY,
    feedback_id TEXT NOT NULL REFERENCES feedback(id) ON DELETE CASCADE,
    kind TEXT NOT NULL,
    question_id TEXT NOT NULL REFERENCES questions(id),
    excerpt TEXT,
    note TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_questions_interview ON questions(interview_id, position);
CREATE INDEX IF NOT EXISTS idx_answers_interview ON answers(interview_id);
"""


def _iso(value):
    return value.isoformat() if value is not None else None


def _datetime(value):
    if value is None:
        return None
    from datetime import datetime

    return datetime.fromisoformat(value)


class SQLiteInterviewRepository:
    """Store an aggregate atomically while keeping SQL out of use cases."""

    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        self._connection = sqlite3.connect(self.path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        with self._lock, self._connection:
            self._connection.executescript(SCHEMA)

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def create(self, interview: Interview) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT INTO interviews (
                    id, candidate_alias, position_title, invitation_token_digest,
                    status, evidence_type, consent_given_at, started_at,
                    submitted_at, reviewed_at, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                self._interview_values(interview),
            )
            self._connection.executemany(
                """
                INSERT INTO questions (id, interview_id, prompt, position, required)
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (
                        question.id,
                        question.interview_id,
                        question.prompt,
                        question.position,
                        int(question.required),
                    )
                    for question in interview.questions
                ],
            )

    def save(self, interview: Interview) -> None:
        with self._lock, self._connection:
            cursor = self._connection.execute(
                """
                UPDATE interviews SET
                    candidate_alias = ?, position_title = ?, invitation_token_digest = ?,
                    status = ?, evidence_type = ?, consent_given_at = ?, started_at = ?,
                    submitted_at = ?, reviewed_at = ?, created_at = ?, updated_at = ?
                WHERE id = ?
                """,
                self._interview_values(interview)[1:] + (interview.id,),
            )
            if cursor.rowcount != 1:
                raise LookupError("interview no longer exists")
            for answer in interview.answers.values():
                self._connection.execute(
                    """
                    INSERT INTO answers (
                        question_id, interview_id, capture_kind, content,
                        media_reference, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(question_id) DO UPDATE SET
                        capture_kind = excluded.capture_kind,
                        content = excluded.content,
                        media_reference = excluded.media_reference,
                        updated_at = excluded.updated_at
                    """,
                    (
                        answer.question_id,
                        answer.interview_id,
                        answer.capture_kind,
                        answer.content,
                        answer.media_reference,
                        _iso(answer.updated_at),
                    ),
                )
            if interview.feedback is not None:
                self._save_feedback(interview.feedback)

    def get_by_id(self, interview_id: str) -> Interview | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM interviews WHERE id = ?",
                (interview_id,),
            ).fetchone()
            return self._hydrate(row) if row else None

    def get_by_token_digest(self, token_digest: str) -> Interview | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM interviews WHERE invitation_token_digest = ?",
                (token_digest,),
            ).fetchone()
            return self._hydrate(row) if row else None

    def list_interviews(self) -> list[Interview]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM interviews ORDER BY updated_at DESC"
            ).fetchall()
            return [self._hydrate(row) for row in rows]

    @staticmethod
    def _interview_values(interview: Interview) -> tuple:
        return (
            interview.id,
            interview.candidate_alias,
            interview.position_title,
            interview.invitation_token_digest,
            interview.status.value,
            interview.evidence_type,
            _iso(interview.consent_given_at),
            _iso(interview.started_at),
            _iso(interview.submitted_at),
            _iso(interview.reviewed_at),
            _iso(interview.created_at),
            _iso(interview.updated_at),
        )

    def _save_feedback(self, feedback: Feedback) -> None:
        self._connection.execute(
            """
            INSERT INTO feedback (
                id, interview_id, candidate_summary, strengths_json, risks_json,
                next_steps, internal_notes, ai_recommendation, recruiter_decision,
                manager_decision, publication_status, version, published_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(interview_id) DO UPDATE SET
                id = excluded.id,
                candidate_summary = excluded.candidate_summary,
                strengths_json = excluded.strengths_json,
                risks_json = excluded.risks_json,
                next_steps = excluded.next_steps,
                internal_notes = excluded.internal_notes,
                ai_recommendation = excluded.ai_recommendation,
                recruiter_decision = excluded.recruiter_decision,
                manager_decision = excluded.manager_decision,
                publication_status = excluded.publication_status,
                version = excluded.version,
                published_at = excluded.published_at,
                updated_at = excluded.updated_at
            """,
            (
                feedback.id,
                feedback.interview_id,
                feedback.candidate_summary,
                json.dumps(feedback.strengths, ensure_ascii=False),
                json.dumps(feedback.risks, ensure_ascii=False),
                feedback.next_steps,
                feedback.internal_notes,
                feedback.ai_recommendation,
                feedback.recruiter_decision,
                feedback.manager_decision.value,
                feedback.publication_status.value,
                feedback.version,
                _iso(feedback.published_at),
                _iso(feedback.updated_at),
            ),
        )
        self._connection.execute("DELETE FROM evidence WHERE feedback_id = ?", (feedback.id,))
        self._connection.executemany(
            """
            INSERT INTO evidence (id, feedback_id, kind, question_id, excerpt, note)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    item.id,
                    item.feedback_id,
                    item.kind.value,
                    item.question_id,
                    item.excerpt,
                    item.note,
                )
                for item in feedback.evidence
            ],
        )

    def _hydrate(self, row: sqlite3.Row) -> Interview:
        question_rows = self._connection.execute(
            "SELECT * FROM questions WHERE interview_id = ? ORDER BY position",
            (row["id"],),
        ).fetchall()
        answer_rows = self._connection.execute(
            "SELECT * FROM answers WHERE interview_id = ?",
            (row["id"],),
        ).fetchall()
        questions = tuple(
            Question(
                id=item["id"],
                interview_id=item["interview_id"],
                prompt=item["prompt"],
                position=item["position"],
                required=bool(item["required"]),
            )
            for item in question_rows
        )
        answers = {
            item["question_id"]: Answer(
                interview_id=item["interview_id"],
                question_id=item["question_id"],
                capture_kind=item["capture_kind"],
                content=item["content"],
                media_reference=item["media_reference"],
                updated_at=_datetime(item["updated_at"]),
            )
            for item in answer_rows
        }
        feedback = self._load_feedback(row["id"])
        return Interview(
            id=row["id"],
            candidate_alias=row["candidate_alias"],
            position_title=row["position_title"],
            invitation_token_digest=row["invitation_token_digest"],
            questions=questions,
            status=InterviewStatus(row["status"]),
            evidence_type=row["evidence_type"],
            consent_given_at=_datetime(row["consent_given_at"]),
            started_at=_datetime(row["started_at"]),
            submitted_at=_datetime(row["submitted_at"]),
            reviewed_at=_datetime(row["reviewed_at"]),
            created_at=_datetime(row["created_at"]),
            updated_at=_datetime(row["updated_at"]),
            answers=answers,
            feedback=feedback,
        )

    def _load_feedback(self, interview_id: str) -> Feedback | None:
        row = self._connection.execute(
            "SELECT * FROM feedback WHERE interview_id = ?",
            (interview_id,),
        ).fetchone()
        if row is None:
            return None
        evidence_rows = self._connection.execute(
            "SELECT * FROM evidence WHERE feedback_id = ? ORDER BY rowid",
            (row["id"],),
        ).fetchall()
        evidence = tuple(
            Evidence(
                id=item["id"],
                feedback_id=item["feedback_id"],
                kind=EvidenceKind(item["kind"]),
                question_id=item["question_id"],
                excerpt=item["excerpt"],
                note=item["note"],
            )
            for item in evidence_rows
        )
        return Feedback(
            id=row["id"],
            interview_id=row["interview_id"],
            candidate_summary=row["candidate_summary"],
            strengths=tuple(json.loads(row["strengths_json"])),
            risks=tuple(json.loads(row["risks_json"])),
            next_steps=row["next_steps"],
            internal_notes=row["internal_notes"],
            ai_recommendation=row["ai_recommendation"],
            recruiter_decision=row["recruiter_decision"],
            manager_decision=ManagerDecision(row["manager_decision"]),
            publication_status=PublicationStatus(row["publication_status"]),
            evidence=evidence,
            version=row["version"],
            published_at=_datetime(row["published_at"]),
            updated_at=_datetime(row["updated_at"]),
        )
