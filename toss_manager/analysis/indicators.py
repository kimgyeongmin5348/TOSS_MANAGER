"""Technical indicator calculations using only historical candle values."""

import pandas as pd


def add_indicators(candles: pd.DataFrame) -> pd.DataFrame:
    frame = candles.sort_values("timestamp").drop_duplicates("timestamp").copy()
    close = frame["close_price"].astype(float)
    high = frame["high_price"].astype(float)
    low = frame["low_price"].astype(float)
    volume = frame["volume"].astype(float)

    frame["return"] = close.pct_change()
    frame["ema20"] = close.ewm(span=20, adjust=False).mean()
    frame["ema60"] = close.ewm(span=60, adjust=False).mean()
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    frame["macd"] = ema12 - ema26
    frame["macd_signal"] = frame["macd"].ewm(span=9, adjust=False).mean()
    frame["macd_hist"] = frame["macd"] - frame["macd_signal"]

    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    rs = gain / loss.replace(0, float("nan"))
    frame["rsi14"] = (100 - (100 / (1 + rs))).where(loss.ne(0), 100)

    frame["volume_ma20"] = volume.rolling(20).mean()
    frame["volume_ratio"] = volume / frame["volume_ma20"]
    frame["bb_mid"] = close.rolling(20).mean()
    deviation = close.rolling(20).std(ddof=0)
    frame["bb_upper"] = frame["bb_mid"] + 2 * deviation
    frame["bb_lower"] = frame["bb_mid"] - 2 * deviation

    previous_close = close.shift(1)
    true_range = pd.concat(
        [(high - low), (high - previous_close).abs(), (low - previous_close).abs()],
        axis=1,
    ).max(axis=1)
    frame["atr14"] = true_range.ewm(alpha=1 / 14, adjust=False).mean()
    frame["atr_ratio"] = frame["atr14"] / close
    frame["atr_median60"] = frame["atr_ratio"].rolling(60).median()
    return frame
