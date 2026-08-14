import unittest
from unittest.mock import Mock, patch

from toss_manager.config import FundamentalsSettings
from toss_manager.fundamentals.service import _kr_values, load_company_fundamentals


class FundamentalsTests(unittest.TestCase):
    def test_maps_dart_ifrs_accounts(self) -> None:
        values = _kr_values([
            {"sj_div": "IS", "account_id": "ifrs-full_Revenue", "thstrm_amount": "1,000"},
            {"sj_div": "IS", "account_id": "dart_OperatingIncomeLoss", "thstrm_amount": "200"},
            {"sj_div": "IS", "account_id": "ifrs-full_ProfitLoss", "thstrm_amount": "100"},
            {"sj_div": "BS", "account_id": "ifrs-full_Assets", "thstrm_amount": "2,000"},
            {"sj_div": "BS", "account_id": "ifrs-full_Liabilities", "thstrm_amount": "800"},
            {"sj_div": "BS", "account_id": "ifrs-full_Equity", "thstrm_amount": "1,200"},
            {"sj_div": "SCE", "account_id": "ifrs-full_Equity", "thstrm_amount": "12"},
        ])
        self.assertEqual(values["revenue"], 1000)
        self.assertEqual(values["net_income"], 100)

    @patch("toss_manager.fundamentals.service.OpenDartFinancialProvider")
    def test_calculates_valuation_from_price_shares_and_filing(self, provider: Mock) -> None:
        provider.return_value.fetch.return_value = (2025, "CFS", [
            {"sj_div": "IS", "account_id": "ifrs-full_Revenue", "thstrm_amount": "1000"},
            {"sj_div": "IS", "account_id": "ifrs-full_ProfitLoss", "thstrm_amount": "100"},
            {"sj_div": "BS", "account_id": "ifrs-full_Equity", "thstrm_amount": "500"},
        ])
        result = load_company_fundamentals(
            symbol="005930", market_country="KR", market_price=10,
            shares_outstanding=100, settings=FundamentalsSettings(opendart_api_key="key"),
        )
        self.assertEqual(result.market_cap, 1000)
        self.assertEqual(result.per_ratio, 10)
        self.assertEqual(result.pbr_ratio, 2)
        self.assertEqual(result.psr_ratio, 1)
        self.assertEqual(result.roe_pct, 20)

    @patch("toss_manager.fundamentals.service.OpenDartFinancialProvider")
    def test_loss_company_has_no_per(self, provider: Mock) -> None:
        provider.return_value.fetch.return_value = (2025, "CFS", [
            {"sj_div": "IS", "account_id": "ifrs-full_ProfitLoss", "thstrm_amount": "-10"},
        ])
        result = load_company_fundamentals(
            symbol="000000", market_country="KR", market_price=10,
            shares_outstanding=100, settings=FundamentalsSettings(opendart_api_key="key"),
        )
        self.assertIsNone(result.per_ratio)


if __name__ == "__main__":
    unittest.main()
