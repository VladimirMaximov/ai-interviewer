import unittest

from app.domain.interview_state import SessionStatus, begin_session, submit_session


class InterviewStateTests(unittest.TestCase):
    def test_consented_session_can_begin_and_submit(self) -> None:
        status = begin_session(SessionStatus.NOT_STARTED, consented=True)
        self.assertEqual(submit_session(status, required_answers_complete=True), SessionStatus.SUBMITTED)

    def test_session_requires_consent_and_answers(self) -> None:
        with self.assertRaises(ValueError):
            begin_session(SessionStatus.NOT_STARTED, consented=False)
        with self.assertRaises(ValueError):
            submit_session(SessionStatus.IN_PROGRESS, required_answers_complete=False)
