from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text


class HiringContextMigrationTests(unittest.TestCase):
    def test_upgrade_and_downgrade_add_context_tables_and_columns(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "migration.sqlite3"
            config = Config("backend/alembic.ini")
            config.set_main_option("sqlalchemy.url", f"sqlite+pysqlite:///{database}")

            command.upgrade(config, "head")
            engine = create_engine(f"sqlite+pysqlite:///{database}")
            inspector = inspect(engine)
            self.assertTrue(
                {"vacancies", "candidate_resumes"}.issubset(
                    inspector.get_table_names()
                )
            )
            invitation_columns = {
                item["name"]
                for item in inspector.get_columns("interview_invitations")
            }
            self.assertTrue(
                {"vacancy_id", "candidate_alias", "created_by"}.issubset(
                    invitation_columns
                )
            )
            resume_columns = {
                item["name"] for item in inspector.get_columns("candidate_resumes")
            }
            self.assertTrue(
                {"uploaded_by_role", "uploaded_by_actor_id"}.issubset(
                    resume_columns
                )
            )

            command.downgrade(config, "002_manager_brief")
            inspector = inspect(engine)
            self.assertNotIn("candidate_resumes", inspector.get_table_names())
            self.assertNotIn("vacancies", inspector.get_table_names())
            engine.dispose()

    def test_existing_resume_is_backfilled_as_candidate_upload(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "backfill.sqlite3"
            config = Config("backend/alembic.ini")
            config.set_main_option("sqlalchemy.url", f"sqlite+pysqlite:///{database}")
            command.upgrade(config, "003_vacancy_resume_context")
            engine = create_engine(f"sqlite+pysqlite:///{database}")
            vacancy_id = uuid4().hex
            invitation_id = uuid4().hex
            resume_id = uuid4().hex
            now = datetime.now(timezone.utc).isoformat()
            with engine.begin() as connection:
                connection.execute(
                    text(
                        """
                        INSERT INTO vacancies (
                            id, title, source_filename, media_type, byte_size,
                            extracted_text, content_hash, status, created_by,
                            idempotency_key, created_at
                        ) VALUES (
                            :id, 'Synthetic vacancy', 'vacancy.txt', 'text/plain',
                            9, 'Synthetic', :hash, 'active', 'recruiter-test',
                            'migration-vacancy', :created_at
                        )
                        """
                    ),
                    {"id": vacancy_id, "hash": "a" * 64, "created_at": now},
                )
                connection.execute(
                    text(
                        """
                        INSERT INTO interview_invitations (
                            id, token_digest, vacancy_id, expires_at, status
                        ) VALUES (
                            :id, :digest, :vacancy_id, :expires_at, 'active'
                        )
                        """
                    ),
                    {
                        "id": invitation_id,
                        "digest": "b" * 64,
                        "vacancy_id": vacancy_id,
                        "expires_at": now,
                    },
                )
                connection.execute(
                    text(
                        """
                        INSERT INTO candidate_resumes (
                            id, invitation_id, vacancy_id, version,
                            source_filename, media_type, byte_size,
                            extracted_text, content_hash, idempotency_key,
                            created_at
                        ) VALUES (
                            :id, :invitation_id, :vacancy_id, 1,
                            'resume.txt', 'text/plain', 9, 'Synthetic',
                            :hash, 'migration-resume', :created_at
                        )
                        """
                    ),
                    {
                        "id": resume_id,
                        "invitation_id": invitation_id,
                        "vacancy_id": vacancy_id,
                        "hash": "c" * 64,
                        "created_at": now,
                    },
                )

            command.upgrade(config, "head")
            with engine.connect() as connection:
                row = connection.execute(
                    text(
                        """
                        SELECT uploaded_by_role, uploaded_by_actor_id
                        FROM candidate_resumes WHERE id = :id
                        """
                    ),
                    {"id": resume_id},
                ).one()
            self.assertEqual(row.uploaded_by_role, "candidate")
            self.assertIsNone(row.uploaded_by_actor_id)
            engine.dispose()


if __name__ == "__main__":
    unittest.main()
