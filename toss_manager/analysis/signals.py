"""Convert continuous indicators into explainable discrete states."""

import pandas as pd


SIGNAL_COLUMNS = ("ema_signal", "macd_signal_state", "rsi_signal", "volume_signal", "bollinger_signal")


def add_signals(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    ema20_up = result["ema20"].diff() > 0
    ema60_up = result["ema60"].diff() > 0
    result["ema_signal"] = 0
    result.loc[(result["ema20"] > result["ema60"]) & ema20_up & ema60_up, "ema_signal"] = 1
    result.loc[(result["ema20"] < result["ema60"]) & ~ema20_up & ~ema60_up, "ema_signal"] = -1

    result["macd_signal_state"] = 0
    result.loc[(result["macd"] > result["macd_signal"]) & (result["macd_hist"].diff() > 0), "macd_signal_state"] = 1
    result.loc[(result["macd"] < result["macd_signal"]) & (result["macd_hist"].diff() < 0), "macd_signal_state"] = -1

    result["rsi_signal"] = 0
    result.loc[result["rsi14"].between(50, 70) & (result["rsi14"].diff() > 0), "rsi_signal"] = 1
    result.loc[result["rsi14"].between(30, 50) & (result["rsi14"].diff() < 0), "rsi_signal"] = -1
    result.loc[result["rsi14"] > 75, "rsi_signal"] = -1

    result["volume_signal"] = 0
    result.loc[(result["volume_ratio"] >= 1.2) & (result["return"] > 0), "volume_signal"] = 1
    result.loc[(result["volume_ratio"] >= 1.2) & (result["return"] < 0), "volume_signal"] = -1

    result["bollinger_signal"] = 0
    result.loc[(result["close_price"] > result["bb_mid"]) & (result["close_price"] <= result["bb_upper"]), "bollinger_signal"] = 1
    result.loc[(result["close_price"] < result["bb_mid"]) & (result["close_price"] >= result["bb_lower"]), "bollinger_signal"] = -1
    return result
