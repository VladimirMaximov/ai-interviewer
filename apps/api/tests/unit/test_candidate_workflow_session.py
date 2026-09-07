import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

from sqlalchemy.exc import IntegrityError

from app.models.interview import InvitationStatus
from app.services.candidate_workflow import SqlCandidateWorkflow


class CandidateWorkflowSessionTests(unittest.TestCase):
    def test_concurrent_session_insert_reuses_committed_session(self) -> None:
        invitation = SimpleNamespace(
            id=uuid4(),
            status=InvitationStatus.ACTIVE,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        concurrent_session = SimpleNamespace(invitation_id=invitation.id)
        database = MagicMock()
        database.scalar.side_effect = [invitation, None, concurrent_session]
        database.commit.side_effect = IntegrityError("insert", {}, Exception())

        workflow = SqlCandidateWorkflow(database, MagicMock())

        self.assertIs(workflow._session("valid-secret"), concurrent_session)
        database.rollback.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
