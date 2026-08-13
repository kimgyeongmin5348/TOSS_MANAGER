"""Historical same-signal and similar-signal outcome statistics."""

import pandas as pd

from .models import BacktestResult
from .signals import SIGNAL_COLUMNS


def evaluate_history(frame: pd.DataFrame, threshold: float = 0.002) -> BacktestResult:
    history = frame.iloc[:-1].copy()
    current = frame.iloc[-1]
    history["next_return"] = history["close_price"].shift(-1) / history["close_price"] - 1
    history = history.dropna(subset=["next_return", *SIGNAL_COLUMNS])
    exact = history.loc[(history[list(SIGNAL_COLUMNS)] == current[list(SIGNAL_COLUMNS)].values).all(axis=1)]
    match_type = "동일"
    matches = exact
    if len(matches) < 30:
        similarity = (history[list(SIGNAL_COLUMNS)] == current[list(SIGNAL_COLUMNS)].values).mean(axis=1)
        matches = history.loc[similarity >= 0.8]
        match_type = "유사"

    rises = int((matches["next_return"] > threshold).sum())
    falls = int((matches["next_return"] < -threshold).sum())
    flats = int(len(matches) - rises - falls)
    rise_rate = rises / len(matches) * 100 if len(matches) else None
    base_rises = int((history["next_return"] > threshold).sum())
    base_rate = base_rises / len(history) * 100 if len(history) else None
    return BacktestResult(match_type, len(matches), rises, falls, flats, rise_rate, base_rate)
