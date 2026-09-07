import tempfile
import unittest
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


class ManagerBriefMigrationTests(unittest.TestCase):
    def test_upgrade_and_downgrade_create_only_additive_manager_tables(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "migration.sqlite3"
            config = Config("apps/api/alembic.ini")
            config.set_main_option("sqlalchemy.url", f"sqlite+pysqlite:///{database}")

            command.upgrade(config, "head")
            engine = create_engine(f"sqlite+pysqlite:///{database}")
            tables = set(inspect(engine).get_table_names())
            self.assertTrue(
                {
                    "interview_invitations",
                    "manager_brief_operations",
                    "manager_brief_agent_runs",
                    "manager_brief_drafts",
                }.issubset(tables)
            )

            command.downgrade(config, "001_interview_core")
            tables = set(inspect(engine).get_table_names())
            self.assertIn("interview_invitations", tables)
            self.assertNotIn("manager_brief_drafts", tables)
            engine.dispose()


if __name__ == "__main__":
    unittest.main()
