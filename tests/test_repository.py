import unittest

from sqlalchemy import create_engine, text

from toss_manager.repository import mask_account_number, search_instruments


class AccountMaskTests(unittest.TestCase):
    def test_masks_all_but_last_four_characters(self) -> None:
        self.assertEqual(mask_account_number("1234-5678-9012"), "********9012")

    def test_short_value_still_has_mask(self) -> None:
        self.assertEqual(mask_account_number("123"), "****123")

    def test_empty_value_returns_none(self) -> None:
        self.assertIsNone(mask_account_number(None))
        self.assertIsNone(mask_account_number("---"))


class InstrumentSearchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite://")
        with self.engine.begin() as connection:
            connection.execute(text("""
                CREATE TABLE instruments (
                    symbol TEXT, market_country TEXT,
                    name TEXT, english_name TEXT
                )
            """))
            connection.execute(text("""
                INSERT INTO instruments
                  (symbol, market_country, name, english_name)
                VALUES
                  ('BZAI', 'US', '블레이즈 홀딩스', 'Blaize Holdings'),
                  ('005930', 'KR', '삼성전자', 'Samsung Electronics')
            """))

    def test_searches_korean_company_name(self) -> None:
        result = search_instruments(
            self.engine, query="블레이즈 홀딩스", market_country="US"
        )
        self.assertEqual(result[0]["symbol"], "BZAI")

    def test_does_not_cross_market_boundary(self) -> None:
        result = search_instruments(
            self.engine, query="삼성전자", market_country="US"
        )
        self.assertEqual(result, [])

if __name__ == "__main__":
    unittest.main()
