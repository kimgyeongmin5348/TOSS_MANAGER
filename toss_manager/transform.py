"""Turn nested API payloads into analysis/storage-friendly tables."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pandas as pd


def holdings_frame(payload: dict[str, Any], account_seq: int) -> pd.DataFrame:
    rows = []
    # TiDB DATETIME has no timezone field; store an explicitly documented naive UTC value.
    captured_at = datetime.now(timezone.utc).replace(tzinfo=None)
    for item in payload.get("items", []):
        rows.append({
            "account_seq": account_seq,
            "symbol": item["symbol"],
            "name": item.get("name"),
            "market_country": item.get("marketCountry"),
            "currency": item.get("currency"),
            "quantity": item.get("quantity"),
            "last_price": item.get("lastPrice"),
            "average_purchase_price": item.get("averagePurchasePrice"),
            "purchase_amount": item.get("marketValue", {}).get("purchaseAmount"),
            "market_value": item.get("marketValue", {}).get("amount"),
            "profit_loss": item.get("profitLoss", {}).get("amount"),
            "profit_loss_rate": item.get("profitLoss", {}).get("rate"),
            "daily_profit_loss": item.get("dailyProfitLoss", {}).get("amount"),
            "daily_profit_loss_rate": item.get("dailyProfitLoss", {}).get("rate"),
            "captured_at": captured_at,
        })
    frame = pd.DataFrame(rows)
    numeric = [
        "quantity", "last_price", "average_purchase_price", "purchase_amount",
        "market_value", "profit_loss", "profit_loss_rate", "daily_profit_loss",
        "daily_profit_loss_rate",
    ]
    for column in numeric:
        if column in frame:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame


def candles_frame(payload: dict[str, Any], symbol: str, interval: str) -> pd.DataFrame:
    frame = pd.DataFrame(payload.get("candles", []))
    if frame.empty:
        return frame
    frame = frame.rename(columns={
        "openPrice": "open_price", "highPrice": "high_price",
        "lowPrice": "low_price", "closePrice": "close_price",
    })
    frame.insert(0, "symbol", symbol.upper())
    frame.insert(1, "interval", interval)
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
    for column in ["open_price", "high_price", "low_price", "close_price", "volume"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame.sort_values("timestamp").reset_index(drop=True)
