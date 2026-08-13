"""Shared UI formatting and chart data helpers."""

import pandas as pd


PERIODS = {
    "1분": ("1m", None, 120),
    "5분": ("1m", "5min", 200),
    "10분": ("1m", "10min", 200),
    "1일": ("1d", None, 120),
    "주": ("1d", "W-FRI", 200),
    "월": ("1d", "ME", 200),
    "년": ("1d", "YE", 200),
}


def currency(value: float, market: str) -> str:
    return f"${value:,.2f}" if market == "US" else f"₩{value:,.0f}"


def aggregate_candles(frame: pd.DataFrame, rule: str | None) -> pd.DataFrame:
    if frame.empty or not rule:
        return frame
    indexed = frame.set_index("timestamp")
    return (
        indexed.resample(rule)
        .agg(
            open_price=("open_price", "first"),
            high_price=("high_price", "max"),
            low_price=("low_price", "min"),
            close_price=("close_price", "last"),
            volume=("volume", "sum"),
        )
        .dropna(subset=["open_price", "close_price"])
        .reset_index()
    )
