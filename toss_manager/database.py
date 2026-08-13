"""TiDB connection and schema management."""

from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import Engine, create_engine, inspect, text
from sqlalchemy.engine import URL

from .config import DatabaseSettings


SCHEMA_STATEMENTS = (
    """CREATE TABLE IF NOT EXISTS app_users (
      user_id BIGINT NOT NULL AUTO_INCREMENT,
      email VARCHAR(320) NOT NULL,
      display_name VARCHAR(100),
      timezone VARCHAR(64) NOT NULL DEFAULT 'Asia/Seoul',
      base_currency VARCHAR(8) NOT NULL DEFAULT 'KRW',
      created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
      updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
      PRIMARY KEY (user_id), UNIQUE KEY uq_app_users_email (email)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci""",
    """CREATE TABLE IF NOT EXISTS brokerage_accounts (
      account_id BIGINT NOT NULL AUTO_INCREMENT,
      user_id BIGINT NOT NULL,
      provider VARCHAR(32) NOT NULL DEFAULT 'TOSS_SECURITIES',
      toss_account_seq BIGINT NOT NULL,
      account_no_masked VARCHAR(64), account_type VARCHAR(64),
      is_active BOOLEAN NOT NULL DEFAULT TRUE,
      created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
      updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
      PRIMARY KEY (account_id),
      UNIQUE KEY uq_brokerage_provider_account (provider, toss_account_seq),
      KEY ix_brokerage_accounts_user_id (user_id),
      CONSTRAINT fk_brokerage_accounts_user FOREIGN KEY (user_id) REFERENCES app_users(user_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci""",
    """CREATE TABLE IF NOT EXISTS instruments (
      instrument_id BIGINT NOT NULL AUTO_INCREMENT,
      symbol VARCHAR(32) NOT NULL, market VARCHAR(32) NOT NULL,
      market_country VARCHAR(8) NOT NULL, currency VARCHAR(8) NOT NULL,
      name VARCHAR(255), english_name VARCHAR(255), isin_code VARCHAR(32),
      security_type VARCHAR(64), status VARCHAR(32),
      is_common_share BOOLEAN, shares_outstanding DECIMAL(30,10),
      leverage_factor DECIMAL(20,10), list_date DATE, delist_date DATE,
      created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
      updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
      PRIMARY KEY (instrument_id),
      UNIQUE KEY uq_instruments_symbol_market (symbol, market),
      KEY ix_instruments_isin_code (isin_code)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci""",
    """CREATE TABLE IF NOT EXISTS portfolio_snapshots (
      snapshot_id BIGINT NOT NULL AUTO_INCREMENT, account_id BIGINT NOT NULL,
      captured_at DATETIME(6) NOT NULL,
      total_purchase_krw DECIMAL(30,10), total_purchase_usd DECIMAL(30,10),
      market_value_krw DECIMAL(30,10), market_value_usd DECIMAL(30,10),
      profit_loss_krw DECIMAL(30,10), profit_loss_usd DECIMAL(30,10),
      profit_loss_rate DECIMAL(20,10), daily_profit_loss_rate DECIMAL(20,10),
      created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
      PRIMARY KEY (snapshot_id), UNIQUE KEY uq_portfolio_account_captured (account_id, captured_at),
      CONSTRAINT fk_portfolio_snapshots_account FOREIGN KEY (account_id) REFERENCES brokerage_accounts(account_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci""",
    """CREATE TABLE IF NOT EXISTS holding_snapshot_items (
      snapshot_id BIGINT NOT NULL, instrument_id BIGINT NOT NULL, currency VARCHAR(8) NOT NULL,
      quantity DECIMAL(30,10), last_price DECIMAL(30,10), average_purchase_price DECIMAL(30,10),
      purchase_amount DECIMAL(30,10), market_value DECIMAL(30,10), market_value_after_cost DECIMAL(30,10),
      profit_loss DECIMAL(30,10), profit_loss_after_cost DECIMAL(30,10),
      profit_loss_rate DECIMAL(20,10), profit_loss_rate_after_cost DECIMAL(20,10),
      daily_profit_loss DECIMAL(30,10), daily_profit_loss_rate DECIMAL(20,10),
      commission DECIMAL(30,10), tax DECIMAL(30,10),
      created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
      PRIMARY KEY (snapshot_id, instrument_id), KEY ix_holding_items_instrument (instrument_id),
      CONSTRAINT fk_holding_items_snapshot FOREIGN KEY (snapshot_id) REFERENCES portfolio_snapshots(snapshot_id),
      CONSTRAINT fk_holding_items_instrument FOREIGN KEY (instrument_id) REFERENCES instruments(instrument_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci""",
    """CREATE TABLE IF NOT EXISTS price_snapshots (
      instrument_id BIGINT NOT NULL, captured_at DATETIME(6) NOT NULL,
      market_timestamp DATETIME(6), last_price DECIMAL(30,10) NOT NULL, currency VARCHAR(8) NOT NULL,
      created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
      PRIMARY KEY (instrument_id, captured_at),
      CONSTRAINT fk_price_snapshots_instrument FOREIGN KEY (instrument_id) REFERENCES instruments(instrument_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci""",
    """CREATE TABLE IF NOT EXISTS candles (
      instrument_id BIGINT NOT NULL, interval_code VARCHAR(8) NOT NULL, candle_at DATETIME(6) NOT NULL,
      open_price DECIMAL(30,10), high_price DECIMAL(30,10), low_price DECIMAL(30,10),
      close_price DECIMAL(30,10), volume DECIMAL(30,10), currency VARCHAR(8) NOT NULL,
      adjusted BOOLEAN NOT NULL DEFAULT TRUE,
      created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
      updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
      PRIMARY KEY (instrument_id, interval_code, candle_at),
      CONSTRAINT fk_candles_instrument FOREIGN KEY (instrument_id) REFERENCES instruments(instrument_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci""",
    """CREATE TABLE IF NOT EXISTS exchange_rates (
      base_currency VARCHAR(8) NOT NULL, quote_currency VARCHAR(8) NOT NULL, rate_at DATETIME(6) NOT NULL,
      exchange_rate DECIMAL(30,10) NOT NULL, source VARCHAR(64),
      created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
      PRIMARY KEY (base_currency, quote_currency, rate_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci""",
    """CREATE TABLE IF NOT EXISTS watchlist_items (
      user_id BIGINT NOT NULL, instrument_id BIGINT NOT NULL, memo VARCHAR(1000),
      target_price DECIMAL(30,10), created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
      PRIMARY KEY (user_id, instrument_id), KEY ix_watchlist_instrument (instrument_id),
      CONSTRAINT fk_watchlist_user FOREIGN KEY (user_id) REFERENCES app_users(user_id),
      CONSTRAINT fk_watchlist_instrument FOREIGN KEY (instrument_id) REFERENCES instruments(instrument_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci""",
)

EXPECTED_COLUMNS = {
    "app_users": {"user_id", "email"},
    "brokerage_accounts": {"account_id", "user_id", "toss_account_seq"},
    "instruments": {"instrument_id", "symbol", "market"},
    "portfolio_snapshots": {"snapshot_id", "account_id", "captured_at"},
    "holding_snapshot_items": {"snapshot_id", "instrument_id"},
    "price_snapshots": {"instrument_id", "captured_at"},
    "candles": {"instrument_id", "interval_code", "candle_at"},
    "exchange_rates": {"base_currency", "quote_currency", "rate_at"},
    "watchlist_items": {"user_id", "instrument_id"},
}


def make_engine(settings: DatabaseSettings | str | URL) -> Engine:
    url = settings.url if isinstance(settings, DatabaseSettings) else settings
    return create_engine(url, pool_pre_ping=True, pool_recycle=300, connect_args={"connect_timeout": 10})


def check_connection(engine: Engine) -> None:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))


def initialize_schema(engine: Engine, statements: Iterable[str] = SCHEMA_STATEMENTS) -> None:
    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))
    validate_schema(engine)


def validate_schema(engine: Engine) -> None:
    schema = inspect(engine)
    problems = []
    for table, required in EXPECTED_COLUMNS.items():
        actual = {column["name"] for column in schema.get_columns(table)} if schema.has_table(table) else set()
        if missing := required - actual:
            problems.append(f"{table}: {', '.join(sorted(missing))}")
    if problems:
        raise RuntimeError("README ERD와 다른 기존 테이블이 있습니다: " + "; ".join(problems))
