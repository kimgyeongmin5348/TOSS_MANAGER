import unittest

from toss_manager.auth import hash_password, verify_password


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


if __name__ == "__main__":
    unittest.main()
