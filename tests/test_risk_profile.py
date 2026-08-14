import unittest
from datetime import datetime, timedelta, timezone

import pandas as pd

from toss_manager.risk_profile import analyze_portfolio_risk, build_llm_risk_context


def candles(start: float, daily_change: float, count: int = 80) -> pd.DataFrame:
    prices = [start]
    for _ in range(count - 1):
        prices.append(prices[-1] * (1 + daily_change))
    return pd.DataFrame({
        "timestamp": [datetime.now(timezone.utc) - timedelta(days=count - i) for i in range(count)],
        "close_price": prices,
    })


class RiskProfileTests(unittest.TestCase):
    def test_concentrated_leveraged_portfolio_scores_higher(self) -> None:
        safe = pd.DataFrame([
            {"symbol": "A", "market_value": 50, "currency": "KRW", "leverage_factor": 1},
            {"symbol": "B", "market_value": 50, "currency": "KRW", "leverage_factor": 1},
        ])
        aggressive = pd.DataFrame([
            {"symbol": "LEV", "market_value": 95, "currency": "USD", "leverage_factor": 3},
            {"symbol": "CASH", "market_value": 5, "currency": "KRW", "leverage_factor": 1},
        ])
        safe_profile = analyze_portfolio_risk(safe, {"A": candles(100, .001), "B": candles(100, -.0005)})
        aggressive_profile = analyze_portfolio_risk(
            aggressive, {"LEV": candles(100, .02), "CASH": candles(100, 0)}
        )
        self.assertGreater(aggressive_profile.score, safe_profile.score)
        self.assertEqual(aggressive_profile.features.leveraged_weight_pct, 95.0)

    def test_duplicate_symbol_is_one_concentration_position(self) -> None:
        holdings = pd.DataFrame([
            {"symbol": "A", "market_value": 40, "currency": "KRW", "leverage_factor": 1},
            {"symbol": "A", "market_value": 60, "currency": "KRW", "leverage_factor": 1},
        ])
        profile = analyze_portfolio_risk(holdings, {"A": candles(100, .001)})
        self.assertEqual(profile.features.holdings_count, 1)
        self.assertEqual(profile.features.top1_weight_pct, 100.0)

    def test_llm_context_has_no_identity_and_declares_unknowns(self) -> None:
        holdings = pd.DataFrame([
            {"symbol": "A", "market_value": 100, "currency": "KRW", "leverage_factor": 1},
        ])
        context = build_llm_risk_context(analyze_portfolio_risk(holdings, {}))
        self.assertEqual(context["schema_version"], "porto.observed-risk.v1")
        self.assertNotIn("email", str(context).lower())
        self.assertIn("투자 목적", context["unknown_user_factors"])


if __name__ == "__main__":
    unittest.main()
