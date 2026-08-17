import unittest

from sqlalchemy import create_engine, text

from toss_manager.watchlist import get_watchlist_item


class WatchlistIsolationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite://")
        with self.engine.begin() as connection:
            connection.execute(text("""
                CREATE TABLE instruments (
                  instrument_id INTEGER PRIMARY KEY, symbol TEXT, name TEXT,
                  market_country TEXT, currency TEXT
                )
            """))
            connection.execute(text("""
                CREATE TABLE watchlist_items (
                  user_id INTEGER, instrument_id INTEGER, memo TEXT,
                  target_price NUMERIC, last_price NUMERIC, price_updated_at DATETIME
                )
            """))
            connection.execute(text("""
                INSERT INTO instruments
                  (instrument_id, symbol, name, market_country, currency)
                VALUES (1, 'AAPL', 'Apple', 'US', 'USD')
            """))
            connection.execute(text("""
                INSERT INTO watchlist_items
                  (user_id, instrument_id, memo, target_price, last_price)
                VALUES
                  (10, 1, 'first user', 250, 200),
                  (20, 1, 'second user', 300, 200)
            """))

    def test_same_instrument_is_isolated_by_user(self) -> None:
        first = get_watchlist_item(
            self.engine, user_id=10, symbol="AAPL", market_country="US"
        )
        second = get_watchlist_item(
            self.engine, user_id=20, symbol="AAPL", market_country="US"
        )
        self.assertEqual(first["memo"], "first user")
        self.assertEqual(second["memo"], "second user")
        self.assertNotEqual(first["target_price"], second["target_price"])


if __name__ == "__main__":
    unittest.main()
