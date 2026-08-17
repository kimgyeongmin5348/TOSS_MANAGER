import unittest
from datetime import datetime, timezone

import pandas as pd

from toss_manager.snapshots import closing_snapshot_types, holdings_fingerprint


class SnapshotPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.holdings = pd.DataFrame([
            {
                "symbol": "AAPL", "market_country": "US", "currency": "USD",
                "quantity": 2.0, "last_price": 200.0,
                "average_purchase_price": 150.0, "purchase_amount": 300.0,
                "market_value": 400.0, "profit_loss": 100.0,
                "profit_loss_rate": 0.333, "daily_profit_loss": 2.0,
                "daily_profit_loss_rate": 0.005,
            },
            {
                "symbol": "005930", "market_country": "KR", "currency": "KRW",
                "quantity": 1.0, "last_price": 100000.0,
            },
        ])

    def test_fingerprint_is_independent_of_row_order_and_timestamp(self) -> None:
        changed_order = self.holdings.iloc[::-1].copy()
        changed_order["captured_at"] = datetime.now(timezone.utc)
        self.assertEqual(
            holdings_fingerprint(self.holdings), holdings_fingerprint(changed_order)
        )

    def test_fingerprint_changes_with_holding_values(self) -> None:
        changed = self.holdings.copy()
        changed.loc[0, "quantity"] = 3.0
        self.assertNotEqual(
            holdings_fingerprint(self.holdings), holdings_fingerprint(changed)
        )

    def test_close_window_is_market_specific(self) -> None:
        now = datetime(2026, 8, 17, 7, 0, tzinfo=timezone.utc)
        self.assertEqual(closing_snapshot_types(self.holdings, now), ["CLOSE_KR"])


if __name__ == "__main__":
    unittest.main()
