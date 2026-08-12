"""TiDB persistence through its MySQL-compatible SQLAlchemy driver."""

from __future__ import annotations

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS holding_snapshots (
  account_seq BIGINT NOT NULL,
  symbol VARCHAR(32) NOT NULL,
  name VARCHAR(255), market_country VARCHAR(8), currency VARCHAR(8),
  quantity DECIMAL(30,10), last_price DECIMAL(30,10),
  average_purchase_price DECIMAL(30,10), purchase_amount DECIMAL(30,10),
  market_value DECIMAL(30,10), profit_loss DECIMAL(30,10),
  profit_loss_rate DECIMAL(20,10), daily_profit_loss DECIMAL(30,10),
  daily_profit_loss_rate DECIMAL(20,10), captured_at DATETIME(6) NOT NULL,
  PRIMARY KEY (account_seq, symbol, captured_at)
);
CREATE TABLE IF NOT EXISTS candles (
  symbol VARCHAR(32) NOT NULL, interval_code VARCHAR(4) NOT NULL,
  timestamp DATETIME(6) NOT NULL, open_price DECIMAL(30,10),
  high_price DECIMAL(30,10), low_price DECIMAL(30,10),
  close_price DECIMAL(30,10), volume DECIMAL(30,10), currency VARCHAR(8),
  PRIMARY KEY (symbol, interval_code, timestamp)
);
"""


def make_engine(database_url: str) -> Engine:
    return create_engine(database_url, pool_pre_ping=True, pool_recycle=300)


def initialize_schema(engine: Engine) -> None:
    with engine.begin() as connection:
        for statement in SCHEMA_SQL.split(";"):
            if statement.strip():
                connection.execute(text(statement))


def save_holdings(engine: Engine, frame: pd.DataFrame) -> None:
    if not frame.empty:
        frame.to_sql("holding_snapshots", engine, if_exists="append", index=False, method="multi")


def save_candles(engine: Engine, frame: pd.DataFrame) -> None:
    if frame.empty:
        return
    db_frame = frame.rename(columns={"interval": "interval_code"}).copy()
    # Convert timezone-aware pandas values to naive UTC for TiDB DATETIME.
    db_frame["timestamp"] = pd.to_datetime(db_frame["timestamp"], utc=True).dt.tz_localize(None)
    records = db_frame.to_dict("records")
    sql = text("""
        INSERT INTO candles
          (symbol, interval_code, timestamp, open_price, high_price, low_price,
           close_price, volume, currency)
        VALUES
          (:symbol, :interval_code, :timestamp, :open_price, :high_price, :low_price,
           :close_price, :volume, :currency)
        ON DUPLICATE KEY UPDATE
          open_price=VALUES(open_price), high_price=VALUES(high_price),
          low_price=VALUES(low_price), close_price=VALUES(close_price),
          volume=VALUES(volume), currency=VALUES(currency)
    """)
    with engine.begin() as connection:
        connection.execute(sql, records)
