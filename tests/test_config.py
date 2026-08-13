import os
import unittest
from unittest.mock import patch

from sqlalchemy.engine import URL

from toss_manager.config import DatabaseSettings


class DatabaseSettingsTests(unittest.TestCase):
    def test_full_url_takes_priority(self) -> None:
        env = {
            "TIDB_DATABASE_URL": "mysql+pymysql://user:secret@db.example/test",
            "DB_HOST": "ignored.example",
        }
        with patch("toss_manager.config.load_dotenv"), patch.dict(os.environ, env, clear=True):
            settings = DatabaseSettings.from_env()
        self.assertEqual(settings.url, env["TIDB_DATABASE_URL"])

    def test_split_values_create_safe_sqlalchemy_url(self) -> None:
        env = {
            "DB_HOST": "db.example",
            "DB_PORT": "4000",
            "DB_USERNAME": "user",
            "DB_PASSWORD": "p@ss:/word",
            "DB_DATABASE": "portfolio",
            "DB_SSL": "true",
        }
        with patch("toss_manager.config.load_dotenv"), patch.dict(os.environ, env, clear=True):
            settings = DatabaseSettings.from_env()
        self.assertIsInstance(settings.url, URL)
        self.assertEqual(settings.url.password, "p@ss:/word")
        self.assertEqual(settings.url.port, 4000)
        self.assertEqual(settings.url.database, "portfolio")
        self.assertEqual(settings.url.query["ssl_verify_identity"], "true")

    def test_missing_split_value_is_reported(self) -> None:
        with patch("toss_manager.config.load_dotenv"), patch.dict(os.environ, {"DB_HOST": "db.example"}, clear=True):
            with self.assertRaisesRegex(ValueError, "DB_USERNAME"):
                DatabaseSettings.from_env()


if __name__ == "__main__":
    unittest.main()
