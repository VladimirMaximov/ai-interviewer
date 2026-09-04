import tempfile
import unittest
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


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

            command.downgrade(config, "002_manager_brief")
            inspector = inspect(engine)
            self.assertNotIn("candidate_resumes", inspector.get_table_names())
            self.assertNotIn("vacancies", inspector.get_table_names())
            engine.dispose()


if __name__ == "__main__":
    unittest.main()
