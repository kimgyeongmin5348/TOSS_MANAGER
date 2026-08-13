"""Analysis result models."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Evidence:
    key: str
    label: str
    state: int
    description: str
    points: float
    maximum: float


@dataclass(frozen=True)
class BacktestResult:
    match_type: str
    occurrences: int
    rises: int
    falls: int
    flats: int
    rise_rate: float | None
    base_rise_rate: float | None


@dataclass(frozen=True)
class AnalysisResult:
    score: int
    direction: str
    evidence: tuple[Evidence, ...]
    backtest: BacktestResult
    candle_count: int
    analyzed_at: object
