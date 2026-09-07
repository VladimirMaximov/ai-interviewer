"""Prepare deterministic local data for the short product demonstration."""

from datetime import datetime, timezone
from hashlib import sha256
from uuid import uuid4

from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from app.config import settings
from app.domain.hiring_context import VacancyStatus
from app.models.hiring_context import Vacancy


DEMO_TITLE = "Быстрое демо-интервью"
DEMO_KEY = "quick-demo-vacancy-v1"


def question(block_key: str, prompt: str, kind: str, position: int) -> dict:
    item = {
        "id": str(uuid4()),
        "text": prompt,
        "kind": kind,
        "follow_up_after_answer": False,
        "time_limit_seconds": 45 if kind == "spoken" else 120,
        "position": position,
    }
    if kind == "coding":
        item["language"] = "python"
    return {
        "id": str(uuid4()),
        "title": {
            "hard_skills": "Hard skills",
            "soft_skills": "Soft skills",
            "work_experience": "Опыт работы",
        }[block_key],
        "topic": "Короткая демонстрация",
        "key": block_key,
        "questions": [item],
        "position": position,
    }


def clean_candidates(db: Session) -> None:
    db.execute(text("""
        CREATE TEMP TABLE demo_target_invitations ON COMMIT DROP AS
        SELECT invitation.id
        FROM interview_invitations AS invitation
        JOIN vacancies AS vacancy ON vacancy.id = invitation.vacancy_id
        WHERE (
            vacancy.title = 'Middle+ Python Developer'
            AND invitation.candidate_alias NOT LIKE 'Обезличенный кандидат%'
        ) OR (
            vacancy.title = 'Junior ML Developer'
            AND lower(invitation.candidate_alias) = 'ккк'
        );
        CREATE TEMP TABLE demo_target_sessions ON COMMIT DROP AS
        SELECT id FROM interview_sessions
        WHERE invitation_id IN (SELECT id FROM demo_target_invitations);
        CREATE TEMP TABLE demo_target_agents ON COMMIT DROP AS
        SELECT id FROM agent_sessions
        WHERE invitation_id IN (SELECT id FROM demo_target_invitations);
        CREATE TEMP TABLE demo_target_responses ON COMMIT DROP AS
        SELECT id FROM candidate_responses
        WHERE session_id IN (SELECT id FROM demo_target_sessions);
        CREATE TEMP TABLE demo_target_recordings ON COMMIT DROP AS
        SELECT id FROM interview_recordings
        WHERE session_id IN (SELECT id FROM demo_target_sessions);
        CREATE TEMP TABLE demo_target_operations ON COMMIT DROP AS
        SELECT id FROM agent_operations
        WHERE agent_session_id IN (SELECT id FROM demo_target_agents);
        CREATE TEMP TABLE demo_target_artifacts ON COMMIT DROP AS
        SELECT id FROM agent_artifacts
        WHERE agent_session_id IN (SELECT id FROM demo_target_agents);

        DELETE FROM candidate_feedback_releases
        WHERE invitation_id IN (SELECT id FROM demo_target_invitations)
           OR agent_session_id IN (SELECT id FROM demo_target_agents)
           OR feedback_artifact_id IN (SELECT id FROM demo_target_artifacts);
        DELETE FROM ranking_entries
        WHERE agent_session_id IN (SELECT id FROM demo_target_agents)
           OR profile_artifact_id IN (SELECT id FROM demo_target_artifacts);
        DELETE FROM agent_runs
        WHERE operation_id IN (SELECT id FROM demo_target_operations);
        DELETE FROM agent_artifacts
        WHERE id IN (SELECT id FROM demo_target_artifacts);
        DELETE FROM agent_operations
        WHERE id IN (SELECT id FROM demo_target_operations);
        DELETE FROM runtime_evaluation_jobs
        WHERE response_id IN (SELECT id FROM demo_target_responses);
        DELETE FROM code_answers
        WHERE response_id IN (SELECT id FROM demo_target_responses);
        DELETE FROM interview_voice_profiles
        WHERE session_id IN (SELECT id FROM demo_target_sessions)
           OR first_response_id IN (SELECT id FROM demo_target_responses)
           OR second_response_id IN (SELECT id FROM demo_target_responses);
        DELETE FROM interview_monitoring_events
        WHERE session_id IN (SELECT id FROM demo_target_sessions);
        DELETE FROM interview_follow_up_questions
        WHERE session_id IN (SELECT id FROM demo_target_sessions);
        DELETE FROM interview_recording_chunks
        WHERE recording_id IN (SELECT id FROM demo_target_recordings);
        DELETE FROM interview_timeline_events
        WHERE session_id IN (SELECT id FROM demo_target_sessions);
        DELETE FROM candidate_responses
        WHERE id IN (SELECT id FROM demo_target_responses);
        DELETE FROM interview_recordings
        WHERE id IN (SELECT id FROM demo_target_recordings);
        DELETE FROM agent_sessions
        WHERE id IN (SELECT id FROM demo_target_agents);
        DELETE FROM candidate_resumes
        WHERE invitation_id IN (SELECT id FROM demo_target_invitations);
        DELETE FROM question_avatar_assets
        WHERE invitation_id IN (SELECT id FROM demo_target_invitations);
        DELETE FROM restriction_decisions
        WHERE invitation_id IN (SELECT id FROM demo_target_invitations);
        DELETE FROM interview_sessions
        WHERE id IN (SELECT id FROM demo_target_sessions);
        DELETE FROM interview_invitations
        WHERE id IN (SELECT id FROM demo_target_invitations);
    """))


def set_demo_scores(db: Session) -> None:
    db.execute(text("""
        WITH targets(candidate_alias, normalized_score) AS (
            VALUES ('Обезличенный кандидат 1', 0.7::float),
                   ('Обезличенный кандидат 2', 0.2::float)
        ),
        response_positions AS (
            SELECT
                agent.id AS agent_session_id,
                invitation.candidate_alias,
                artifact.payload::jsonb->>'response_id' AS response_id,
                target.normalized_score,
                row_number() OVER (
                    PARTITION BY agent.id
                    ORDER BY artifact.payload::jsonb->>'response_id'
                ) AS position,
                count(*) OVER (PARTITION BY agent.id) AS response_count
            FROM agent_artifacts AS artifact
            JOIN agent_sessions AS agent ON agent.id = artifact.agent_session_id
            JOIN interview_invitations AS invitation ON invitation.id = agent.invitation_id
            JOIN vacancies AS vacancy ON vacancy.id = agent.vacancy_id
            JOIN targets AS target ON target.candidate_alias = invitation.candidate_alias
            WHERE vacancy.title = 'Middle+ Python Developer'
              AND artifact.kind = 'answer_assessment'
            GROUP BY
                agent.id,
                invitation.candidate_alias,
                artifact.payload::jsonb->>'response_id',
                target.normalized_score
        ),
        artifacts AS (
            SELECT
                artifact.id,
                positions.normalized_score
                    + (
                        positions.position
                        - (positions.response_count + 1)::float / 2
                    ) * 0.06 AS question_score
            FROM agent_artifacts AS artifact
            JOIN agent_sessions AS agent ON agent.id = artifact.agent_session_id
            JOIN interview_invitations AS invitation ON invitation.id = agent.invitation_id
            JOIN vacancies AS vacancy ON vacancy.id = agent.vacancy_id
            JOIN response_positions AS positions
              ON positions.agent_session_id = agent.id
             AND positions.response_id = artifact.payload::jsonb->>'response_id'
            WHERE vacancy.title = 'Middle+ Python Developer'
              AND artifact.kind = 'answer_assessment'
        )
        UPDATE agent_artifacts AS artifact
        SET payload = jsonb_set(
            artifact.payload::jsonb,
            '{observations}',
            COALESCE((
                SELECT jsonb_agg(
                    jsonb_set(
                        jsonb_set(item, '{value}', to_jsonb(artifacts.question_score)),
                        '{label}',
                        to_jsonb('supported'::text)
                    )
                )
                FROM jsonb_array_elements(artifact.payload::jsonb->'observations') AS item
            ), '[]'::jsonb)
        )::json
        FROM artifacts
        WHERE artifact.id = artifacts.id;

        WITH targets(candidate_alias, normalized_score) AS (
            VALUES ('Обезличенный кандидат 1', 0.7::float),
                   ('Обезличенный кандидат 2', 0.2::float)
        )
        UPDATE agent_artifacts AS artifact
        SET payload = jsonb_set(
            artifact.payload::jsonb,
            '{overall_readiness}',
            to_jsonb(target.normalized_score)
        )::json
        FROM agent_sessions AS agent
        JOIN interview_invitations AS invitation ON invitation.id = agent.invitation_id
        JOIN vacancies AS vacancy ON vacancy.id = agent.vacancy_id
        JOIN targets AS target ON target.candidate_alias = invitation.candidate_alias
        WHERE artifact.agent_session_id = agent.id
          AND vacancy.title = 'Middle+ Python Developer'
          AND artifact.kind = 'candidate_profile';

        WITH targets(candidate_alias, normalized_score) AS (
            VALUES ('Обезличенный кандидат 1', 0.7::float),
                   ('Обезличенный кандидат 2', 0.2::float)
        )
        UPDATE ranking_entries AS entry
        SET overall_value = target.normalized_score
        FROM agent_sessions AS agent
        JOIN interview_invitations AS invitation ON invitation.id = agent.invitation_id
        JOIN vacancies AS vacancy ON vacancy.id = agent.vacancy_id
        JOIN targets AS target ON target.candidate_alias = invitation.candidate_alias
        WHERE entry.agent_session_id = agent.id
          AND vacancy.title = 'Middle+ Python Developer';
    """))


def create_demo_vacancy(db: Session) -> Vacancy:
    vacancy = db.scalar(
        select(Vacancy).where(
            Vacancy.created_by == "demo-recruiter",
            Vacancy.idempotency_key == DEMO_KEY,
        )
    )
    description = (
        "Короткая демонстрационная вакансия для проверки полного сценария "
        "интервью без длительных ответов."
    )
    config = {
        "schema_version": 1,
        "blocks": [
            question("hard_skills", "Напишите функцию, которая возвращает сумму двух чисел.", "coding", 0),
            question("soft_skills", "Как вы себя чувствуете?", "spoken", 1),
            question("work_experience", "Кратко расскажите про опыт работы.", "spoken", 2),
        ],
        "follow_up_after_all_answers": False,
        "live_coding_enabled": True,
    }
    if vacancy is None:
        vacancy = Vacancy(
            title=DEMO_TITLE,
            source_filename="quick-demo-vacancy.txt",
            media_type="text/plain",
            byte_size=len(description.encode()),
            extracted_text=description,
            content_hash=sha256(description.encode()).hexdigest(),
            status=VacancyStatus.ACTIVE,
            created_by="demo-recruiter",
            idempotency_key=DEMO_KEY,
            created_at=datetime.now(timezone.utc),
            interview_config=config,
            interview_config_revision=1,
        )
        db.add(vacancy)
    else:
        vacancy.extracted_text = description
        vacancy.interview_config = config
        vacancy.interview_config_revision += 1
    return vacancy


def main() -> None:
    engine = create_engine(settings.database_url)
    with Session(engine) as db, db.begin():
        clean_candidates(db)
        set_demo_scores(db)
        vacancy = create_demo_vacancy(db)
        vacancy_id, vacancy_title = vacancy.id, vacancy.title
    print(f"Prepared demo vacancy: {vacancy_id} — {vacancy_title}")


if __name__ == "__main__":
    main()
