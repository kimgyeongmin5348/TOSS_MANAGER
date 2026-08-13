import unittest

import pandas as pd

from toss_manager.analysis import analyze_candles


def sample_candles(count: int = 200) -> pd.DataFrame:
    rows = []
    for index in range(count):
        close = 100 + index * 0.3 + ((index % 7) - 3) * 0.2
        rows.append({
            "timestamp": pd.Timestamp("2025-01-01", tz="UTC") + pd.Timedelta(days=index),
            "open_price": close - 0.2, "high_price": close + 1,
            "low_price": close - 1, "close_price": close,
            "volume": 1000 + index * 5,
        })
    return pd.DataFrame(rows)


class AnalysisTests(unittest.TestCase):
    def test_returns_bounded_score_and_evidence(self) -> None:
        result = analyze_candles(sample_candles())
        self.assertGreaterEqual(result.score, 0)
        self.assertLessEqual(result.score, 100)
        self.assertEqual(len(result.evidence), 7)
        self.assertIn(result.direction, {"상승 우세", "중립", "하락 우세"})

    def test_history_counts_are_consistent(self) -> None:
        stats = analyze_candles(sample_candles()).backtest
        self.assertEqual(stats.occurrences, stats.rises + stats.falls + stats.flats)

    def test_rejects_short_history(self) -> None:
        with self.assertRaisesRegex(ValueError, "최소"):
            analyze_candles(sample_candles(40))


if __name__ == "__main__":
    unittest.main()
