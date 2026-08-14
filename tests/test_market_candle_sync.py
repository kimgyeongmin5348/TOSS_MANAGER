import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

import pandas as pd

from toss_manager.ui.market import sync_daily_candles


class MarketCandleSyncTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = Mock()
        self.engine = Mock()
        self.incoming = pd.DataFrame({
            "timestamp": pd.to_datetime(["2026-08-14T00:00:00Z"]),
            "interval": ["1d"],
            "open_price": [1], "high_price": [1], "low_price": [1],
            "close_price": [1], "volume": [1], "currency": ["USD"],
        })

    @patch("toss_manager.ui.market.load_candles", return_value=[])
    @patch("toss_manager.ui.market.upsert_candles")
    @patch("toss_manager.ui.market.candles_frame")
    @patch("toss_manager.ui.market.candle_coverage")
    def test_partial_history_triggers_five_year_backfill(
        self, coverage, candles_frame, upsert, load
    ) -> None:
        coverage.return_value = {
            "first_at": datetime.now(timezone.utc) - timedelta(days=120),
            "last_at": datetime.now(timezone.utc),
            "candle_count": 120,
        }
        self.client.get_candle_history.return_value = {"candles": []}
        candles_frame.return_value = self.incoming

        sync_daily_candles(self.client, self.engine, "QQQ", "US", {})

        self.client.get_candle_history.assert_called_once_with(
            "QQQ", interval="1d", years=5
        )
        self.client.get_candles_since.assert_not_called()
        upsert.assert_called_once()

    @patch("toss_manager.ui.market.load_candles", return_value=[])
    @patch("toss_manager.ui.market.upsert_candles")
    @patch("toss_manager.ui.market.candles_frame")
    @patch("toss_manager.ui.market.candle_coverage")
    def test_complete_history_uses_incremental_refresh(
        self, coverage, candles_frame, upsert, load
    ) -> None:
        latest = datetime.now(timezone.utc) - timedelta(days=1)
        coverage.return_value = {
            "first_at": datetime.now(timezone.utc) - timedelta(days=1900),
            "last_at": latest,
            "candle_count": 1221,
        }
        self.client.get_candles_since.return_value = {"candles": []}
        candles_frame.return_value = self.incoming

        sync_daily_candles(self.client, self.engine, "005930", "KR", {})

        self.client.get_candles_since.assert_called_once_with(
            "005930", since=latest, interval="1d"
        )
        self.client.get_candle_history.assert_not_called()
        upsert.assert_called_once()


if __name__ == "__main__":
    unittest.main()
