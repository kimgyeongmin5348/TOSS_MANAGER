"""Deterministic 100-point scoring with human-readable evidence."""

from .models import Evidence


def score_latest(row, previous) -> tuple[int, tuple[Evidence, ...]]:
    definitions = (
        ("macd", "MACD", "macd_signal_state", 20, _macd_text),
        ("ema", "EMA", "ema_signal", 25, _ema_text),
        ("rsi", "RSI", "rsi_signal", 15, _rsi_text),
        ("volume", "거래량", "volume_signal", 15, _volume_text),
        ("bollinger", "볼린저", "bollinger_signal", 10, _bollinger_text),
    )
    evidence = []
    total = 0.0
    for key, label, column, maximum, formatter in definitions:
        state = int(row[column])
        points = maximum if state > 0 else maximum / 2 if state == 0 else 0
        total += points
        evidence.append(Evidence(key, label, state, formatter(row, previous), points, maximum))

    trend_state = 1 if row["close_price"] > row["ema60"] else -1
    trend_points = 10 if trend_state > 0 else 0
    total += trend_points
    evidence.append(Evidence("trend", "중장기 추세", trend_state, "EMA60 위" if trend_state > 0 else "EMA60 아래", trend_points, 10))

    high_volatility = row["atr_ratio"] > row["atr_median60"] * 1.5
    volatility_points = 0 if high_volatility else 5
    total += volatility_points
    evidence.append(Evidence("volatility", "변동성", -1 if high_volatility else 0, "최근 평균보다 높음" if high_volatility else "정상 범위", volatility_points, 5))
    return round(total), tuple(evidence)


def direction_from_score(score: int) -> str:
    if score >= 65:
        return "상승 우세"
    if score <= 35:
        return "하락 우세"
    return "중립"


def _macd_text(row, previous) -> str:
    if row["macd_signal_state"] > 0:
        return "강한 상승 신호"
    if row["macd_signal_state"] < 0:
        return "강한 하락 신호"
    return "방향 확인 중"


def _ema_text(row, previous) -> str:
    return "정배열·상승" if row["ema_signal"] > 0 else "역배열·하락" if row["ema_signal"] < 0 else "혼조"


def _rsi_text(row, previous) -> str:
    return f"{row['rsi14']:.1f} · " + ("상승 모멘텀" if row["rsi_signal"] > 0 else "하락/과열 주의" if row["rsi_signal"] < 0 else "중립")


def _volume_text(row, previous) -> str:
    change = (row["volume_ratio"] - 1) * 100
    return f"20일 평균 대비 {change:+.0f}%"


def _bollinger_text(row, previous) -> str:
    return "중심선 위" if row["bollinger_signal"] > 0 else "중심선 아래" if row["bollinger_signal"] < 0 else "중립/밴드 이탈"
