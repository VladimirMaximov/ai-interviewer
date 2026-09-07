import time
import unittest
from unittest.mock import patch
from uuid import uuid4

from app.security.media_access import create_media_signature, verify_media_signature


class MediaAccessTests(unittest.TestCase):
    def test_default_signature_is_stable_during_same_window(self) -> None:
        vacancy_id, session_id = uuid4(), uuid4()
        with patch("app.security.media_access.time.time", return_value=100):
            first = create_media_signature(vacancy_id, session_id, 0, "secret")
        with patch("app.security.media_access.time.time", return_value=200):
            second = create_media_signature(vacancy_id, session_id, 0, "secret")
        self.assertEqual(first, second)

    def test_valid_signature_is_accepted(self) -> None:
        vacancy_id, session_id = uuid4(), uuid4()
        expires, signature = create_media_signature(
            vacancy_id, session_id, 0, "secret", expires_at=int(time.time()) + 60
        )
        self.assertTrue(
            verify_media_signature(
                vacancy_id, session_id, 0, expires, signature, "secret"
            )
        )

    def test_expired_or_modified_signature_is_rejected(self) -> None:
        vacancy_id, session_id = uuid4(), uuid4()
        expires, signature = create_media_signature(
            vacancy_id, session_id, 0, "secret", expires_at=int(time.time()) - 1
        )
        self.assertFalse(
            verify_media_signature(
                vacancy_id, session_id, 0, expires, signature, "secret"
            )
        )
        self.assertFalse(
            verify_media_signature(
                vacancy_id, session_id, 1, expires + 120, signature, "secret"
            )
        )
