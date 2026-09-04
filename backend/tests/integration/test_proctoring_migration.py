from pathlib import Path
import tempfile
import unittest

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


class ProctoringMigrationTests(unittest.TestCase):
    def test_upgrade_adds_monitoring_tables_and_downgrade_removes_them(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "monitoring.sqlite3"
            config = Config("backend/alembic.ini")
            config.set_main_option(
                "sqlalchemy.url", f"sqlite+pysqlite:///{database}"
            )

            command.upgrade(config, "head")
            engine = create_engine(f"sqlite+pysqlite:///{database}")
            inspector = inspect(engine)
            self.assertTrue(
                {
                    "interview_monitoring_events",
                    "interview_voice_profiles",
                }.issubset(inspector.get_table_names())
            )
            event_columns = {
                item["name"]
                for item in inspector.get_columns("interview_monitoring_events")
            }
            self.assertTrue(
                {
                    "started_at_ms",
                    "ended_at_ms",
                    "review_status",
                    "evidence_storage_key",
                }.issubset(event_columns)
            )

            command.downgrade(config, "006_candidate_feedback_agent")
            inspector = inspect(engine)
            self.assertNotIn(
                "interview_monitoring_events", inspector.get_table_names()
            )
            self.assertNotIn(
                "interview_voice_profiles", inspector.get_table_names()
            )
            engine.dispose()


if __name__ == "__main__":
    unittest.main()
