import unittest

from sqlalchemy import create_engine, text

from toss_manager.accounts import authenticate_with_limit
from toss_manager.auth import LOGIN_FAILURE_LIMIT, hash_password


class LoginLockTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite://")
        with self.engine.begin() as connection:
            connection.execute(text("""
                CREATE TABLE app_users (
                  user_id INTEGER PRIMARY KEY, email TEXT, display_name TEXT,
                  password_hash TEXT, failed_login_count INTEGER DEFAULT 0,
                  locked_until DATETIME, last_login_at DATETIME,
                  session_version INTEGER DEFAULT 1,
                  email_verified BOOLEAN DEFAULT FALSE
                )
            """))
            connection.execute(text("""
                INSERT INTO app_users
                  (user_id, email, display_name, password_hash)
                VALUES (1, 'member@example.com', 'Member', :password_hash)
            """), {"password_hash": hash_password("correct password")})

    def test_fifth_failure_temporarily_locks_account(self) -> None:
        for _ in range(LOGIN_FAILURE_LIMIT - 1):
            self.assertEqual(
                authenticate_with_limit(
                    self.engine, "member@example.com", "wrong password"
                ).status,
                "invalid",
            )
        result = authenticate_with_limit(
            self.engine, "member@example.com", "wrong password"
        )
        self.assertEqual(result.status, "locked")
        self.assertIsNotNone(result.locked_until)

    def test_success_returns_user_and_resets_failure_count(self) -> None:
        result = authenticate_with_limit(
            self.engine, "member@example.com", "correct password"
        )
        self.assertEqual(result.status, "success")
        self.assertEqual(result.user["user_id"], 1)
        with self.engine.connect() as connection:
            failures = connection.execute(text(
                "SELECT failed_login_count FROM app_users WHERE user_id=1"
            )).scalar_one()
        self.assertEqual(failures, 0)


if __name__ == "__main__":
    unittest.main()
