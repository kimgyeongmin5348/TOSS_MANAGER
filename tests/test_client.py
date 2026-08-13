import unittest
from unittest.mock import Mock
from unittest.mock import patch
from datetime import datetime, timedelta, timezone

import requests

from toss_manager.client import TossAPIClient, TossAPIError
from toss_manager.config import Settings


class ClientErrorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TossAPIClient(Settings("client", "secret"))

    def test_timeout_becomes_toss_api_error(self) -> None:
        self.client._access_token = "token"
        from datetime import datetime, timedelta, timezone
        self.client._expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        self.client.session.get = Mock(side_effect=requests.Timeout())
        with self.assertRaisesRegex(TossAPIError, "시간이 초과"):
            self.client.get_prices(["AAPL"])

    def test_invalid_json_becomes_toss_api_error(self) -> None:
        response = Mock(ok=True)
        response.json.side_effect = ValueError("invalid")
        with self.assertRaisesRegex(TossAPIError, "JSON"):
            self.client._json(response)

    @patch("toss_manager.client.time.sleep")
    def test_candle_history_follows_next_before_and_deduplicates(self, sleep) -> None:
        now = datetime.now(timezone.utc)
        shared = (now - timedelta(days=2)).isoformat()
        self.client.get_candles = Mock(side_effect=[
            {"candles": [
                {"timestamp": now.isoformat(), "closePrice": "10"},
                {"timestamp": shared, "closePrice": "9"},
            ], "nextBefore": shared},
            {"candles": [
                {"timestamp": shared, "closePrice": "9"},
                {"timestamp": (now - timedelta(days=3)).isoformat(), "closePrice": "8"},
            ]},
        ])
        result = self.client.get_candle_history("AAPL", years=1)
        self.assertEqual(len(result["candles"]), 3)
        self.assertEqual(self.client.get_candles.call_count, 2)
        sleep.assert_called_once()


if __name__ == "__main__":
    unittest.main()
