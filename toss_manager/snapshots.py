"""Portfolio snapshot policy and persistence.

`captured_at` is the Toss data basis time. `created_at` is the database save time.
Closing snapshots are retained; ordinary intraday snapshots expire after 30 days.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import math
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd
from sqlalchemy import Engine, text


AUTO_INTERVAL = timedelta(minutes=15)
MANUAL_INTERVAL = timedelta(minutes=1)
CLOSE_INTERVAL = timedelta(hours=20)
INTRADAY_RETENTION_DAYS = 30
HASH_FIELDS = (
    "symbol", "market_country", "currency", "quantity", "last_price",
    "average_purchase_price", "purchase_amount", "market_value", "profit_loss",
    "profit_loss_rate", "daily_profit_loss", "daily_profit_loss_rate",
)


@dataclass(frozen=True)
class SnapshotResult:
    status: str
    captured_at: datetime
    saved_at: datetime | None = None
    snapshot_id: int | None = None
    snapshot_type: str = "INTRADAY"

    @property
    def message(self) -> str:
        return {
            "saved": "DB 저장 완료",
            "duplicate": "보유 내역이 같아 중복 저장하지 않음",
            "rate_limited": "저장 간격 제한으로 건너뜀",
        }.get(self.status, self.status)


def holdings_fingerprint(holdings: pd.DataFrame) -> str:
    """Hash only normalized holdings values, independent of row order and timestamps."""
    records: list[dict[str, Any]] = []
    for row in holdings.to_dict("records"):
        normalized: dict[str, Any] = {}
        for field in HASH_FIELDS:
            value = row.get(field)
            if value is None or (isinstance(value, float) and math.isnan(value)):
                normalized[field] = None
            elif field in {"symbol", "market_country", "currency"}:
                normalized[field] = str(value).upper()
            elif isinstance(value, (int, float)):
                normalized[field] = format(float(value), ".10g")
            else:
                normalized[field] = str(value)
        records.append(normalized)
    records.sort(key=lambda item: (item.get("market_country") or "", item.get("symbol") or ""))
    payload = json.dumps(records, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return sha256(payload.encode("utf-8")).hexdigest()


def holdings_captured_at(holdings: pd.DataFrame, now: datetime | None = None) -> datetime:
    if not holdings.empty and "captured_at" in holdings:
        value = pd.to_datetime(holdings["captured_at"], errors="coerce", utc=True).max()
        if pd.notna(value):
            return value.to_pydatetime().astimezone(timezone.utc).replace(tzinfo=None)
    return (now or datetime.now(timezone.utc)).astimezone(timezone.utc).replace(tzinfo=None)


def closing_snapshot_types(
    holdings: pd.DataFrame, now: datetime | None = None
) -> list[str]:
    """Return market-specific close types only in the two-hour post-close window."""
    current = now or datetime.now(timezone.utc)
    markets = set(holdings.get("market_country", pd.Series(dtype=str)).astype(str).str.upper())
    result: list[str] = []
    for market, zone, close_hour, close_minute in (
        ("KR", "Asia/Seoul", 15, 30),
        ("US", "America/New_York", 16, 0),
    ):
        local = current.astimezone(ZoneInfo(zone))
        minutes = local.hour * 60 + local.minute
        close = close_hour * 60 + close_minute
        if market in markets and local.weekday() < 5 and close <= minutes < close + 120:
            result.append(f"CLOSE_{market}")
    return result


def save_snapshot(
    engine: Engine,
    *,
    user_id: int,
    account_seq: int,
    holdings: pd.DataFrame,
    reason: str = "AUTO",
    snapshot_type: str = "INTRADAY",
    now: datetime | None = None,
) -> SnapshotResult:
    """Save with content de-duplication and reason-aware interval limits."""
    now_utc = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).replace(tzinfo=None)
    captured_at = holdings_captured_at(holdings, now or datetime.now(timezone.utc))
    content_hash = holdings_fingerprint(holdings)
    normalized_reason = reason.upper()[:16]
    normalized_type = snapshot_type.upper()[:16]
    # A close snapshot with unchanged positions is still a new daily record.
    if normalized_type.startswith("CLOSE_"):
        content_hash = sha256(
            f"{content_hash}|{captured_at.date().isoformat()}".encode("utf-8")
        ).hexdigest()
    minimum = (
        CLOSE_INTERVAL if normalized_type.startswith("CLOSE_")
        else MANUAL_INTERVAL if normalized_reason == "MANUAL"
        else timedelta(0) if normalized_reason == "CONNECT"
        else AUTO_INTERVAL
    )

    with engine.begin() as connection:
        account_id = connection.execute(text("""
            SELECT account_id FROM brokerage_accounts
            WHERE user_id=:user_id AND provider='TOSS_SECURITIES'
              AND toss_account_seq=:seq AND is_active=TRUE
        """), {"user_id": user_id, "seq": account_seq}).scalar_one()

        duplicate = connection.execute(text("""
            SELECT snapshot_id, captured_at, created_at FROM portfolio_snapshots
            WHERE account_id=:account_id AND content_hash=:content_hash
              AND snapshot_type=:snapshot_type
            ORDER BY snapshot_id DESC LIMIT 1
        """), {
            "account_id": account_id, "content_hash": content_hash,
            "snapshot_type": normalized_type,
        }).mappings().first()
        if duplicate:
            return SnapshotResult(
                "duplicate", captured_at, duplicate["created_at"],
                int(duplicate["snapshot_id"]), normalized_type,
            )

        latest = connection.execute(text("""
            SELECT created_at FROM portfolio_snapshots
            WHERE account_id=:account_id AND snapshot_type=:snapshot_type
            ORDER BY created_at DESC LIMIT 1
        """), {"account_id": account_id, "snapshot_type": normalized_type}).scalar()
        if latest and minimum and now_utc - latest < minimum:
            return SnapshotResult("rate_limited", captured_at, latest, None, normalized_type)

        totals = _portfolio_totals(holdings)
        result = connection.execute(text("""
            INSERT INTO portfolio_snapshots
              (account_id, captured_at, content_hash, snapshot_type, save_reason,
               total_purchase_krw, total_purchase_usd, market_value_krw,
               market_value_usd, profit_loss_krw, profit_loss_usd, created_at)
            VALUES
              (:account_id, :captured_at, :content_hash, :snapshot_type, :save_reason,
               :purchase_krw, :purchase_usd, :value_krw, :value_usd,
               :profit_krw, :profit_usd, :saved_at)
        """), {
            "account_id": account_id, "captured_at": captured_at,
            "content_hash": content_hash, "snapshot_type": normalized_type,
            "save_reason": normalized_reason, "saved_at": now_utc, **totals,
        })
        snapshot_id = int(result.lastrowid)
        items = _snapshot_items(connection, snapshot_id, holdings)
        if items:
            connection.execute(text("""
                INSERT INTO holding_snapshot_items
                  (snapshot_id, instrument_id, currency, quantity, last_price,
                   average_purchase_price, purchase_amount, market_value, profit_loss,
                   profit_loss_rate, daily_profit_loss, daily_profit_loss_rate)
                VALUES
                  (:snapshot_id, :instrument_id, :currency, :quantity, :last_price,
                   :average_purchase_price, :purchase_amount, :market_value, :profit_loss,
                   :profit_loss_rate, :daily_profit_loss, :daily_profit_loss_rate)
            """), items)
    return SnapshotResult("saved", captured_at, now_utc, snapshot_id, normalized_type)


def latest_snapshot_status(engine: Engine, user_id: int) -> dict[str, Any] | None:
    with engine.connect() as connection:
        row = connection.execute(text("""
            SELECT ps.captured_at, ps.created_at AS saved_at, ps.snapshot_type,
                   ps.save_reason, ba.account_no_masked
            FROM portfolio_snapshots ps
            JOIN brokerage_accounts ba ON ba.account_id=ps.account_id
            WHERE ba.user_id=:user_id
            ORDER BY ps.created_at DESC, ps.snapshot_id DESC LIMIT 1
        """), {"user_id": user_id}).mappings().first()
    return dict(row) if row else None


def cleanup_old_intraday_snapshots(
    engine: Engine, *, retention_days: int = INTRADAY_RETENTION_DAYS,
    now: datetime | None = None,
) -> int:
    cutoff = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).replace(
        tzinfo=None
    ) - timedelta(days=max(1, retention_days))
    with engine.begin() as connection:
        ids = list(connection.execute(text("""
            SELECT snapshot_id FROM portfolio_snapshots
            WHERE snapshot_type='INTRADAY' AND created_at < :cutoff
        """), {"cutoff": cutoff}).scalars())
        if not ids:
            return 0
        connection.execute(text("""
            DELETE FROM holding_snapshot_items WHERE snapshot_id IN (
              SELECT snapshot_id FROM portfolio_snapshots
              WHERE snapshot_type='INTRADAY' AND created_at < :cutoff
            )
        """), {"cutoff": cutoff})
        connection.execute(text("""
            DELETE FROM portfolio_snapshots
            WHERE snapshot_type='INTRADAY' AND created_at < :cutoff
        """), {"cutoff": cutoff})
    return len(ids)


def _snapshot_items(connection: Any, snapshot_id: int, holdings: pd.DataFrame) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for holding in holdings.to_dict("records"):
        market = str(holding.get("market_country") or "UNKNOWN").upper()
        instrument_id = connection.execute(text("""
            SELECT instrument_id FROM instruments
            WHERE symbol=:symbol AND market=:market
        """), {"symbol": str(holding["symbol"]).upper(), "market": market}).scalar_one()
        items.append({
            "snapshot_id": snapshot_id,
            "instrument_id": int(instrument_id),
            "currency": str(holding.get("currency") or "KRW").upper(),
            **{field: _number(holding.get(field)) for field in HASH_FIELDS if field not in {
                "symbol", "market_country", "currency"
            }},
        })
    return items


def _number(value: Any) -> float | None:
    if value is None:
        return None
    number = float(value)
    return None if math.isnan(number) else number


def _portfolio_totals(holdings: pd.DataFrame) -> dict[str, float]:
    totals = {key: 0.0 for key in (
        "purchase_krw", "purchase_usd", "value_krw", "value_usd", "profit_krw", "profit_usd"
    )}
    for holding in holdings.to_dict("records"):
        suffix = "usd" if str(holding.get("currency")).upper() == "USD" else "krw"
        totals[f"purchase_{suffix}"] += _number(holding.get("purchase_amount")) or 0
        totals[f"value_{suffix}"] += _number(holding.get("market_value")) or 0
        totals[f"profit_{suffix}"] += _number(holding.get("profit_loss")) or 0
    return totals
