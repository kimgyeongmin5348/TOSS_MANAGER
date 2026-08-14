"""Persistence operations for users, brokerage accounts, and instruments."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from datetime import datetime, timezone
import math

from sqlalchemy import Engine, text

from .auth import hash_password, verify_password

if TYPE_CHECKING:
    import pandas as pd


def register_user(engine: Engine, email: str, display_name: str, password: str) -> int:
    normalized_email = email.strip().lower()
    if "@" not in normalized_email:
        raise ValueError("올바른 이메일을 입력해 주세요.")
    password_hash = hash_password(password)
    with engine.begin() as connection:
        existing = connection.execute(
            text("SELECT user_id, password_hash FROM app_users WHERE email=:email"),
            {"email": normalized_email},
        ).mappings().first()
        if existing and existing["password_hash"]:
            raise ValueError("이미 가입된 이메일입니다.")
        if existing:
            connection.execute(
                text("UPDATE app_users SET display_name=:name, password_hash=:password WHERE user_id=:id"),
                {"name": display_name.strip() or None, "password": password_hash, "id": existing["user_id"]},
            )
            return int(existing["user_id"])
        result = connection.execute(
            text("INSERT INTO app_users (email, display_name, password_hash) VALUES (:email, :name, :password)"),
            {"email": normalized_email, "name": display_name.strip() or None, "password": password_hash},
        )
        return int(result.lastrowid)


def authenticate_user(engine: Engine, email: str, password: str) -> dict[str, Any] | None:
    with engine.connect() as connection:
        user = connection.execute(
            text("SELECT user_id, email, display_name, password_hash FROM app_users WHERE email=:email"),
            {"email": email.strip().lower()},
        ).mappings().first()
    if not user or not verify_password(password, user["password_hash"]):
        return None
    return {key: user[key] for key in ("user_id", "email", "display_name")}


def mask_account_number(value: Any) -> str | None:
    """Keep only the last four characters of an account number."""
    if value is None:
        return None
    normalized = "".join(character for character in str(value) if character.isalnum())
    if not normalized:
        return None
    visible = normalized[-4:]
    return f"{'*' * max(len(normalized) - len(visible), 4)}{visible}"


def sync_user_and_accounts(
    engine: Engine,
    *,
    email: str,
    display_name: str | None,
    accounts: list[dict[str, Any]],
) -> int:
    """Upsert one app user and every Toss account in a single transaction."""
    normalized_email = email.strip().lower()
    normalized_name = display_name.strip() if display_name else None
    with engine.begin() as connection:
        connection.execute(
            text("""
                INSERT INTO app_users (email, display_name)
                VALUES (:email, :display_name)
                ON DUPLICATE KEY UPDATE
                  display_name=COALESCE(VALUES(display_name), display_name),
                  updated_at=CURRENT_TIMESTAMP(6)
            """),
            {"email": normalized_email, "display_name": normalized_name},
        )
        user_id = connection.execute(
            text("SELECT user_id FROM app_users WHERE email=:email"),
            {"email": normalized_email},
        ).scalar_one()

        statement = text("""
            INSERT INTO brokerage_accounts
              (user_id, provider, toss_account_seq, account_no_masked, account_type, is_active)
            VALUES
              (:user_id, 'TOSS_SECURITIES', :account_seq, :account_no_masked, :account_type, TRUE)
            ON DUPLICATE KEY UPDATE
              account_no_masked=VALUES(account_no_masked),
              account_type=VALUES(account_type),
              is_active=TRUE,
              updated_at=CURRENT_TIMESTAMP(6)
        """)
        records = [
            {
                "user_id": user_id,
                "account_seq": int(account["accountSeq"]),
                "account_no_masked": mask_account_number(account.get("accountNo")),
                "account_type": account.get("accountType"),
            }
            for account in accounts
        ]
        if records:
            connection.execute(statement, records)
    return int(user_id)


def sync_instruments(engine: Engine, holdings: "pd.DataFrame") -> None:
    """Upsert instruments found in the latest holdings response."""
    if holdings.empty:
        return
    records = []
    for holding in holdings.to_dict("records"):
        country = str(holding.get("market_country") or "UNKNOWN").upper()
        currency = str(holding.get("currency") or "KRW").upper()
        records.append(
            {
                "symbol": str(holding["symbol"]).upper(),
                "market": country,
                "market_country": country,
                "currency": currency,
                "name": holding.get("name"),
            }
        )
    with engine.begin() as connection:
        connection.execute(
            text("""
                INSERT INTO instruments
                  (symbol, market, market_country, currency, name)
                VALUES
                  (:symbol, :market, :market_country, :currency, :name)
                ON DUPLICATE KEY UPDATE
                  market_country=VALUES(market_country),
                  currency=VALUES(currency),
                  name=COALESCE(VALUES(name), name),
                  updated_at=CURRENT_TIMESTAMP(6)
            """),
            records,
        )


def upsert_candles(
    engine: Engine,
    *,
    symbol: str,
    market_country: str,
    stock: dict[str, Any],
    candles: "pd.DataFrame",
    adjusted: bool = True,
) -> None:
    """Upsert official Toss 1m/1d candles for one instrument."""
    if candles.empty:
        return
    country = market_country.upper()
    with engine.begin() as connection:
        instrument_id = connection.execute(
            text("""SELECT instrument_id FROM instruments
                    WHERE symbol=:symbol AND market_country=:country
                    ORDER BY instrument_id LIMIT 1"""),
            {"symbol": symbol.upper(), "country": country},
        ).scalar()
        if instrument_id is None:
            result = connection.execute(
                text("""INSERT INTO instruments
                    (symbol, market, market_country, currency, name, english_name,
                     isin_code, security_type, status, is_common_share,
                     shares_outstanding, leverage_factor, list_date, delist_date)
                    VALUES (:symbol, :market, :country, :currency, :name, :english_name,
                     :isin_code, :security_type, :status, :is_common_share,
                     :shares_outstanding, :leverage_factor, :list_date, :delist_date)"""),
                {
                    "symbol": symbol.upper(),
                    "market": stock.get("market") or country,
                    "country": country,
                    "currency": stock.get("currency") or ("USD" if country == "US" else "KRW"),
                    "name": stock.get("name"), "english_name": stock.get("englishName"),
                    "isin_code": stock.get("isinCode"), "security_type": stock.get("securityType"),
                    "status": stock.get("status"), "is_common_share": stock.get("isCommonShare"),
                    "shares_outstanding": stock.get("sharesOutstanding"),
                    "leverage_factor": stock.get("leverageFactor"),
                    "list_date": stock.get("listDate"), "delist_date": stock.get("delistDate"),
                },
            )
            instrument_id = result.lastrowid
        records = candle_records(
            candles, instrument_id=int(instrument_id), adjusted=adjusted
        )
        connection.execute(text("""INSERT INTO candles
            (instrument_id, interval_code, candle_at, open_price, high_price,
             low_price, close_price, volume, currency, adjusted)
            VALUES (:instrument_id, :interval_code, :candle_at, :open_price,
             :high_price, :low_price, :close_price, :volume, :currency, :adjusted)
            ON DUPLICATE KEY UPDATE
             open_price=VALUES(open_price), high_price=VALUES(high_price),
             low_price=VALUES(low_price), close_price=VALUES(close_price),
             volume=VALUES(volume), currency=VALUES(currency),
             adjusted=VALUES(adjusted), updated_at=CURRENT_TIMESTAMP(6)"""), records)


def candle_records(
    candles: "pd.DataFrame", *, instrument_id: int, adjusted: bool
) -> list[dict[str, Any]]:
    """Convert candle frames to timezone-naive UTC database records."""
    records = []
    for candle in candles.to_dict("records"):
        timestamp = candle["timestamp"]
        if getattr(timestamp, "tzinfo", None) is not None:
            timestamp = timestamp.tz_convert("UTC").tz_localize(None)
        records.append({
            "instrument_id": instrument_id,
            "interval_code": candle["interval"],
            "candle_at": timestamp,
            "open_price": _number(candle.get("open_price")),
            "high_price": _number(candle.get("high_price")),
            "low_price": _number(candle.get("low_price")),
            "close_price": _number(candle.get("close_price")),
            "volume": _number(candle.get("volume")),
            "currency": candle.get("currency") or "KRW",
            "adjusted": adjusted,
        })
    return records


def save_portfolio_snapshot(
    engine: Engine, *, user_id: int, account_seq: int, holdings: "pd.DataFrame"
) -> int:
    """Save the latest holdings and link them to their instruments."""
    captured_at = datetime.now(timezone.utc).replace(tzinfo=None)
    with engine.begin() as connection:
        account_id = connection.execute(
            text("""SELECT account_id FROM brokerage_accounts
                    WHERE user_id=:user_id AND provider='TOSS_SECURITIES' AND toss_account_seq=:seq"""),
            {"user_id": user_id, "seq": account_seq},
        ).scalar_one()
        totals = _portfolio_totals(holdings)
        result = connection.execute(
            text("""INSERT INTO portfolio_snapshots
                (account_id, captured_at, total_purchase_krw, total_purchase_usd,
                 market_value_krw, market_value_usd, profit_loss_krw, profit_loss_usd)
                VALUES (:account_id, :captured_at, :purchase_krw, :purchase_usd,
                        :value_krw, :value_usd, :profit_krw, :profit_usd)"""),
            {"account_id": account_id, "captured_at": captured_at, **totals},
        )
        snapshot_id = int(result.lastrowid)
        if holdings.empty:
            return snapshot_id
        items = []
        for holding in holdings.to_dict("records"):
            country = str(holding.get("market_country") or "UNKNOWN").upper()
            instrument_id = connection.execute(
                text("SELECT instrument_id FROM instruments WHERE symbol=:symbol AND market=:market"),
                {"symbol": str(holding["symbol"]).upper(), "market": country},
            ).scalar_one()
            items.append({
                "snapshot_id": snapshot_id,
                "instrument_id": instrument_id,
                "currency": str(holding.get("currency") or "KRW").upper(),
                **{name: _number(holding.get(name)) for name in (
                    "quantity", "last_price", "average_purchase_price", "purchase_amount",
                    "market_value", "profit_loss", "profit_loss_rate",
                    "daily_profit_loss", "daily_profit_loss_rate",
                )},
            })
        connection.execute(text("""INSERT INTO holding_snapshot_items
            (snapshot_id, instrument_id, currency, quantity, last_price,
             average_purchase_price, purchase_amount, market_value, profit_loss,
             profit_loss_rate, daily_profit_loss, daily_profit_loss_rate)
            VALUES (:snapshot_id, :instrument_id, :currency, :quantity, :last_price,
             :average_purchase_price, :purchase_amount, :market_value, :profit_loss,
             :profit_loss_rate, :daily_profit_loss, :daily_profit_loss_rate)"""), items)
        return snapshot_id


def load_saved_portfolio(engine: Engine, user_id: int) -> list[dict[str, Any]]:
    with engine.connect() as connection:
        return list(connection.execute(text("""
            SELECT ba.account_no_masked, ba.account_type, ps.captured_at,
                   i.symbol, i.name, i.market_country, h.currency, h.quantity,
                   h.last_price, h.average_purchase_price, h.market_value,
                   h.profit_loss, h.profit_loss_rate
            FROM brokerage_accounts ba
            JOIN portfolio_snapshots ps ON ps.account_id=ba.account_id
            JOIN holding_snapshot_items h ON h.snapshot_id=ps.snapshot_id
            JOIN instruments i ON i.instrument_id=h.instrument_id
            WHERE ba.user_id=:user_id
              AND ps.snapshot_id=(SELECT MAX(p2.snapshot_id) FROM portfolio_snapshots p2 WHERE p2.account_id=ba.account_id)
            ORDER BY ba.account_id, h.market_value DESC
        """), {"user_id": user_id}).mappings())


def load_saved_candles(
    engine: Engine, *, user_id: int, symbol: str, interval: str = "1d"
) -> list[dict[str, Any]]:
    """Load candles only when the instrument belongs to the user's saved holdings."""
    with engine.connect() as connection:
        return list(connection.execute(text("""
            SELECT c.candle_at AS timestamp, c.interval_code AS `interval`,
                   c.open_price, c.high_price, c.low_price, c.close_price,
                   c.volume, c.currency
            FROM candles c
            JOIN instruments i ON i.instrument_id=c.instrument_id
            WHERE i.symbol=:symbol AND c.interval_code=:interval
              AND EXISTS (
                SELECT 1 FROM holding_snapshot_items h
                JOIN portfolio_snapshots ps ON ps.snapshot_id=h.snapshot_id
                JOIN brokerage_accounts ba ON ba.account_id=ps.account_id
                WHERE h.instrument_id=i.instrument_id AND ba.user_id=:user_id
              )
            ORDER BY c.candle_at
        """), {
            "user_id": user_id,
            "symbol": symbol.upper(),
            "interval": interval,
        }).mappings())


def latest_candle_at(
    engine: Engine, *, symbol: str, market_country: str, interval: str = "1d"
) -> datetime | None:
    with engine.connect() as connection:
        return connection.execute(text("""
            SELECT MAX(c.candle_at) FROM candles c
            JOIN instruments i ON i.instrument_id=c.instrument_id
            WHERE i.symbol=:symbol AND i.market_country=:country
              AND c.interval_code=:interval
        """), {
            "symbol": symbol.upper(), "country": market_country.upper(), "interval": interval,
        }).scalar()


def candle_coverage(
    engine: Engine, *, symbol: str, market_country: str, interval: str = "1d"
) -> dict[str, Any]:
    """Return the stored time range and row count for an instrument's candles."""
    with engine.connect() as connection:
        row = connection.execute(text("""
            SELECT MIN(c.candle_at) AS first_at, MAX(c.candle_at) AS last_at,
                   COUNT(*) AS candle_count
            FROM candles c
            JOIN instruments i ON i.instrument_id=c.instrument_id
            WHERE i.symbol=:symbol AND i.market_country=:country
              AND c.interval_code=:interval
        """), {
            "symbol": symbol.upper(), "country": market_country.upper(), "interval": interval,
        }).mappings().one()
    return {
        "first_at": row["first_at"],
        "last_at": row["last_at"],
        "candle_count": int(row["candle_count"] or 0),
    }


def load_candles(
    engine: Engine, *, symbol: str, market_country: str, interval: str = "1d"
) -> list[dict[str, Any]]:
    with engine.connect() as connection:
        return list(connection.execute(text("""
            SELECT c.candle_at AS timestamp, c.interval_code AS `interval`,
                   c.open_price, c.high_price, c.low_price, c.close_price,
                   c.volume, c.currency
            FROM candles c JOIN instruments i ON i.instrument_id=c.instrument_id
            WHERE i.symbol=:symbol AND i.market_country=:country
              AND c.interval_code=:interval
            ORDER BY c.candle_at
        """), {
            "symbol": symbol.upper(), "country": market_country.upper(), "interval": interval,
        }).mappings())


def search_instruments(
    engine: Engine,
    *,
    query: str,
    market_country: str,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Search previously discovered instruments by ticker or company name."""
    normalized = query.strip()
    if not normalized:
        return []
    with engine.connect() as connection:
        return list(connection.execute(text("""
            SELECT symbol, market_country, name, english_name
            FROM instruments
            WHERE market_country=:country
              AND (
                UPPER(symbol)=UPPER(:query)
                OR name LIKE :contains
                OR english_name LIKE :contains
              )
            ORDER BY
              CASE
                WHEN UPPER(symbol)=UPPER(:query) THEN 0
                WHEN name=:query OR english_name=:query THEN 1
                WHEN name LIKE :prefix OR english_name LIKE :prefix THEN 2
                ELSE 3
              END,
              COALESCE(name, english_name, symbol)
            LIMIT :limit
        """), {
            "country": market_country.upper(),
            "query": normalized,
            "contains": f"%{normalized}%",
            "prefix": f"{normalized}%",
            "limit": int(limit),
        }).mappings())


def _number(value: Any) -> float | None:
    if value is None:
        return None
    number = float(value)
    return None if math.isnan(number) else number


def _portfolio_totals(holdings: "pd.DataFrame") -> dict[str, float]:
    totals = {key: 0.0 for key in (
        "purchase_krw", "purchase_usd", "value_krw", "value_usd", "profit_krw", "profit_usd"
    )}
    for holding in holdings.to_dict("records"):
        suffix = "usd" if str(holding.get("currency")).upper() == "USD" else "krw"
        totals[f"purchase_{suffix}"] += _number(holding.get("purchase_amount")) or 0
        totals[f"value_{suffix}"] += _number(holding.get("market_value")) or 0
        totals[f"profit_{suffix}"] += _number(holding.get("profit_loss")) or 0
    return totals
