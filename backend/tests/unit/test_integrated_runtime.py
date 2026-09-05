import unittest
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.interview_config import (
    InterviewInput,
    configuration_digest,
    normalized_snapshot,
)
from app.models.interview import (
    ProcessingJob,
    ProcessingJobKind,
    ProcessingJobStatus,
)
from app.services.job_queue import DurableJobService


def configuration() -> dict:
    return {
        "schema_version": 1,
        "live_coding_enabled": True,
        "blocks": [
            {
                "id": str(uuid4()),
                "key": "hard_skills",
                "title": "Hard skills",
                "topic": "hard_skills",
                "questions": [
                    {
                        "id": str(uuid4()),
                        "text": "Напишите функцию",
                        "kind": "coding",
                        "language": "python",
                    }
                ],
            },
            {
                "id": str(uuid4()),
                "key": "soft_skills",
                "title": "Soft skills",
                "topic": "soft_skills",
                "questions": [],
            },
            {
                "id": str(uuid4()),
                "key": "work_experience",
                "title": "Опыт",
                "topic": "work_experience",
                "questions": [],
            },
        ],
    }


class ConfigurationTests(unittest.TestCase):
    def test_normalizes_positions_and_hashes_deterministically(self) -> None:
        parsed = InterviewInput.model_validate(configuration())
        snapshot = normalized_snapshot(parsed)
        self.assertEqual(snapshot["blocks"][0]["position"], 0)
        self.assertEqual(snapshot["blocks"][0]["questions"][0]["position"], 0)
        self.assertEqual(configuration_digest(parsed), configuration_digest(parsed))

    def test_rejects_spoken_question_with_coding_language(self) -> None:
        value = configuration()
        value["blocks"][0]["questions"][0].update(
            {"kind": "spoken", "language": "python"}
        )
        with self.assertRaises(ValidationError):
            InterviewInput.model_validate(value)

    def test_rejects_an_entirely_empty_interview(self) -> None:
        value = configuration()
        value["blocks"][0]["questions"] = []
        with self.assertRaises(ValidationError):
            InterviewInput.model_validate(value)


class DurableJobTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite://")
        ProcessingJob.__table__.create(self.engine)
        self.db = Session(self.engine)

    def tearDown(self) -> None:
        self.db.close()
        self.engine.dispose()

    def test_create_once_and_retry_to_terminal_failure(self) -> None:
        service = DurableJobService(self.db, max_attempts=2)
        entity_id = uuid4()
        job = service.create_once(
            ProcessingJobKind.PRESENTER_AUDIO, entity_id, "presenter:one"
        )
        duplicate = service.create_once(
            ProcessingJobKind.PRESENTER_AUDIO, entity_id, "presenter:one"
        )
        self.assertEqual(job.id, duplicate.id)
        self.assertTrue(service.start(job))
        service.fail(job, "temporary")
        self.assertEqual(job.status, ProcessingJobStatus.RETRYABLE_FAILED)
        self.assertTrue(service.start(job))
        service.fail(job, "again")
        self.assertEqual(job.status, ProcessingJobStatus.TERMINAL_FAILED)

    def test_recovers_stale_running_job(self) -> None:
        service = DurableJobService(self.db)
        job = service.create_once(
            ProcessingJobKind.TRANSCRIPTION, uuid4(), "transcription:one"
        )
        service.start(job)
        job.started_at = datetime.now(timezone.utc) - timedelta(hours=1)
        self.db.commit()
        self.assertEqual(service.recover_stale(timedelta(minutes=5)), 1)
        self.assertEqual(job.status, ProcessingJobStatus.RETRYABLE_FAILED)


if __name__ == "__main__":
    unittest.main()
