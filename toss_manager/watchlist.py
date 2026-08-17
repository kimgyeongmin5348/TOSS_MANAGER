"""User-scoped watchlist persistence."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Engine, text


def get_watchlist_item(
    engine: Engine, *, user_id: int, symbol: str, market_country: str
) -> dict[str, Any] | None:
    with engine.connect() as connection:
        row = connection.execute(text("""
            SELECT w.memo, w.target_price, w.last_price, w.price_updated_at,
                   i.instrument_id, i.symbol, i.name, i.market_country, i.currency
            FROM watchlist_items w JOIN instruments i ON i.instrument_id=w.instrument_id
            WHERE w.user_id=:user_id AND i.symbol=:symbol AND i.market_country=:country
        """), {
            "user_id": user_id, "symbol": symbol.upper(),
            "country": market_country.upper(),
        }).mappings().first()
    return dict(row) if row else None


def upsert_watchlist_item(
    engine: Engine,
    *,
    user_id: int,
    symbol: str,
    market_country: str,
    name: str | None,
    currency: str,
    memo: str | None = None,
    target_price: float | None = None,
    last_price: float | None = None,
) -> None:
    country = market_country.upper()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with engine.begin() as connection:
        connection.execute(text("""
            INSERT INTO instruments (symbol, market, market_country, currency, name)
            VALUES (:symbol, :market, :country, :currency, :name)
            ON DUPLICATE KEY UPDATE name=COALESCE(VALUES(name), name),
              currency=VALUES(currency), updated_at=CURRENT_TIMESTAMP(6)
        """), {
            "symbol": symbol.upper(), "market": country, "country": country,
            "currency": currency.upper(), "name": name,
        })
        instrument_id = connection.execute(text("""
            SELECT instrument_id FROM instruments
            WHERE symbol=:symbol AND market=:market
        """), {"symbol": symbol.upper(), "market": country}).scalar_one()
        connection.execute(text("""
            INSERT INTO watchlist_items
              (user_id, instrument_id, memo, target_price, last_price, price_updated_at)
            VALUES (:user_id, :instrument_id, :memo, :target_price, :last_price, :updated_at)
            ON DUPLICATE KEY UPDATE memo=VALUES(memo), target_price=VALUES(target_price),
              last_price=COALESCE(VALUES(last_price), last_price),
              price_updated_at=COALESCE(VALUES(price_updated_at), price_updated_at),
              updated_at=CURRENT_TIMESTAMP(6)
        """), {
            "user_id": user_id, "instrument_id": instrument_id,
            "memo": (memo or "").strip()[:1000] or None,
            "target_price": target_price if target_price and target_price > 0 else None,
            "last_price": last_price if last_price and last_price > 0 else None,
            "updated_at": now if last_price and last_price > 0 else None,
        })


def delete_watchlist_item(
    engine: Engine, *, user_id: int, symbol: str, market_country: str
) -> None:
    with engine.begin() as connection:
        connection.execute(text("""
            DELETE w FROM watchlist_items w
            JOIN instruments i ON i.instrument_id=w.instrument_id
            WHERE w.user_id=:user_id AND i.symbol=:symbol AND i.market_country=:country
        """), {
            "user_id": user_id, "symbol": symbol.upper(),
            "country": market_country.upper(),
        })


def load_watchlist(engine: Engine, *, user_id: int) -> list[dict[str, Any]]:
    with engine.connect() as connection:
        rows = connection.execute(text("""
            SELECT i.symbol, i.name, i.market_country, i.currency,
                   w.memo, w.target_price, w.last_price, w.price_updated_at,
                   w.created_at, w.updated_at,
                   (SELECT COUNT(*) FROM news_articles n
                    WHERE n.instrument_id=i.instrument_id
                      AND n.published_at >= UTC_TIMESTAMP(6) - INTERVAL 60 DAY) AS news_count,
                   (SELECT AVG(n.sentiment_score) FROM news_articles n
                    WHERE n.instrument_id=i.instrument_id
                      AND n.published_at >= UTC_TIMESTAMP(6) - INTERVAL 60 DAY) AS news_sentiment,
                   (SELECT n.title FROM news_articles n
                    WHERE n.instrument_id=i.instrument_id
                    ORDER BY n.published_at DESC LIMIT 1) AS latest_news_title
            FROM watchlist_items w JOIN instruments i ON i.instrument_id=w.instrument_id
            WHERE w.user_id=:user_id
            ORDER BY i.market_country, COALESCE(i.name, i.symbol)
        """), {"user_id": user_id}).mappings()
        return [dict(row) for row in rows]


def update_watchlist_prices(
    engine: Engine, *, user_id: int, prices: list[dict[str, Any]]
) -> None:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    records = [
        {
            "user_id": user_id, "symbol": str(item.get("symbol") or "").upper(),
            "last_price": float(item.get("lastPrice") or 0), "updated_at": now,
        }
        for item in prices if item.get("symbol") and float(item.get("lastPrice") or 0) > 0
    ]
    if not records:
        return
    with engine.begin() as connection:
        connection.execute(text("""
            UPDATE watchlist_items w JOIN instruments i ON i.instrument_id=w.instrument_id
            SET w.last_price=:last_price, w.price_updated_at=:updated_at,
                w.updated_at=CURRENT_TIMESTAMP(6)
            WHERE w.user_id=:user_id AND i.symbol=:symbol
        """), records)
