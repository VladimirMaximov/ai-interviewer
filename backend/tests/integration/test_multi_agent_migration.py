import tempfile
import unittest
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


class MultiAgentMigrationTests(unittest.TestCase):
    def test_upgrade_and_downgrade_are_additive(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "multi-agent.sqlite3"
            config = Config("backend/alembic.ini")
            config.set_main_option("sqlalchemy.url", f"sqlite+pysqlite:///{database}")

            command.upgrade(config, "head")
            engine = create_engine(f"sqlite+pysqlite:///{database}")
            inspector = inspect(engine)
            tables = set(inspector.get_table_names())
            expected = {
                "agent_sessions",
                "agent_operations",
                "agent_runs",
                "agent_artifacts",
                "ranking_snapshots",
                "ranking_entries",
                "restriction_decisions",
            }
            self.assertTrue(expected.issubset(tables))
            self.assertTrue(
                {"interview_invitations", "vacancies", "candidate_resumes"}.issubset(
                    tables
                )
            )
            self.assertIn(
                "input_hash",
                {item["name"] for item in inspector.get_columns("agent_sessions")},
            )

            command.downgrade(config, "004_resume_uploader_audit")
            tables = set(inspect(engine).get_table_names())
            self.assertFalse(expected & tables)
            self.assertIn("candidate_resumes", tables)
            engine.dispose()


if __name__ == "__main__":
    unittest.main()
