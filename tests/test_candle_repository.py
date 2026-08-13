import unittest

from toss_manager.repository import upsert_candles


class FakeTimestamp:
    tzinfo = object()

    def tz_convert(self, zone):
        self.zone = zone
        return self

    def tz_localize(self, value):
        self.localized = value
        return "naive-utc"


class FakeFrame:
    empty = False

    def to_dict(self, orient):
        return [{
            "timestamp": FakeTimestamp(), "interval": "1d",
            "open_price": 10, "high_price": 12, "low_price": 9,
            "close_price": 11, "volume": 100, "currency": "USD",
        }]


class FakeResult:
    lastrowid = None

    def scalar(self):
        return 7


class FakeConnection:
    def __init__(self):
        self.calls = []

    def execute(self, statement, params=None):
        self.calls.append((str(statement), params))
        return FakeResult()


class FakeTransaction:
    def __init__(self, connection):
        self.connection = connection

    def __enter__(self):
        return self.connection

    def __exit__(self, *args):
        return False


class FakeEngine:
    def __init__(self):
        self.connection = FakeConnection()

    def begin(self):
        return FakeTransaction(self.connection)


class CandleRepositoryTests(unittest.TestCase):
    def test_existing_instrument_uses_candle_upsert(self) -> None:
        engine = FakeEngine()
        upsert_candles(
            engine, symbol="AAPL", market_country="US", stock={},
            candles=FakeFrame(), adjusted=True,
        )
        self.assertEqual(len(engine.connection.calls), 2)
        sql, records = engine.connection.calls[1]
        self.assertIn("ON DUPLICATE KEY UPDATE", sql)
        self.assertEqual(records[0]["instrument_id"], 7)
        self.assertEqual(records[0]["candle_at"], "naive-utc")
        self.assertEqual(records[0]["interval_code"], "1d")


if __name__ == "__main__":
    unittest.main()
