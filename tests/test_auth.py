import unittest

from toss_manager.auth import (
    hash_password,
    new_account_token,
    verify_account_token,
    verify_password,
)


class PasswordTests(unittest.TestCase):
    def test_password_round_trip(self) -> None:
        encoded = hash_password("correct horse battery staple")
        self.assertTrue(verify_password("correct horse battery staple", encoded))
        self.assertFalse(verify_password("wrong password", encoded))

    def test_hash_uses_unique_salt(self) -> None:
        self.assertNotEqual(hash_password("same password"), hash_password("same password"))

    def test_short_password_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            hash_password("short")

    def test_account_token_is_stored_as_a_digest(self) -> None:
        token, digest, expires_at = new_account_token()
        self.assertNotEqual(token, digest)
        self.assertTrue(verify_account_token(token, digest))
        self.assertFalse(verify_account_token("wrong", digest))
        self.assertIsNotNone(expires_at)


if __name__ == "__main__":
    unittest.main()
