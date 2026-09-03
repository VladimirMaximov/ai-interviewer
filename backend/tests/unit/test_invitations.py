import unittest

from app.security.invitations import create_invitation_secret, digest_invitation_secret
from app.api.errors import invalid_invitation


class InvitationSecretTests(unittest.TestCase):
    def test_secret_is_not_stored_as_plaintext(self) -> None:
        secret = create_invitation_secret()
        self.assertNotEqual(secret, digest_invitation_secret(secret))
        self.assertEqual(digest_invitation_secret(secret), digest_invitation_secret(secret))

    def test_empty_secret_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            digest_invitation_secret("")

    def test_invalid_link_error_does_not_reveal_token_details(self) -> None:
        error = invalid_invitation()
        self.assertEqual(error.status_code, 404)
        self.assertNotIn("token", error.detail.lower())
