"""Analysis orchestration."""

import pandas as pd

from .backtest import evaluate_history
from .indicators import add_indicators
from .models import AnalysisResult
from .scoring import direction_from_score, score_latest
from .signals import add_signals


MINIMUM_CANDLES = 80


def analyze_candles(
    candles: pd.DataFrame, *, return_threshold: float = 0.002
) -> AnalysisResult:
    if len(candles) < MINIMUM_CANDLES:
        raise ValueError(f"분석에는 최소 {MINIMUM_CANDLES}개의 캔들이 필요합니다.")
    if return_threshold <= 0:
        raise ValueError("상승·하락 판정 기준은 0보다 커야 합니다.")
    frame = add_signals(add_indicators(candles)).dropna().reset_index(drop=True)
    if len(frame) < 2:
        raise ValueError("지표 계산에 사용할 유효한 캔들이 부족합니다.")
    latest, previous = frame.iloc[-1], frame.iloc[-2]
    score, evidence = score_latest(latest, previous)
    return AnalysisResult(
        score=score,
        direction=direction_from_score(score),
        evidence=evidence,
        backtest=evaluate_history(frame, threshold=return_threshold),
        candle_count=len(candles),
        analyzed_at=latest["timestamp"],
    )
