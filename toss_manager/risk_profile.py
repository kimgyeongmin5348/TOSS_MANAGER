"""Observed portfolio-risk features and an LLM-ready, non-PII payload."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import math
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class PortfolioRiskFeatures:
    holdings_count: int
    total_market_value: float
    top1_weight_pct: float
    top3_weight_pct: float
    concentration_hhi: float
    effective_holdings: float
    leveraged_weight_pct: float
    foreign_currency_weight_pct: float
    return_observations: int
    annualized_volatility_pct: float | None
    maximum_drawdown_pct: float | None
    historical_var_95_pct: float | None


@dataclass(frozen=True)
class ObservedRiskProfile:
    score: int
    level: str
    confidence: int
    features: PortfolioRiskFeatures
    reasons: tuple[str, ...]
    missing_information: tuple[str, ...]


def _round(value: float, digits: int = 2) -> float:
    return round(float(value), digits)


def analyze_portfolio_risk(
    holdings: pd.DataFrame,
    daily_candles: dict[str, pd.DataFrame],
) -> ObservedRiskProfile:
    """Describe observed portfolio risk; this is not a suitability assessment."""
    if holdings.empty:
        raise ValueError("분석할 저장 포트폴리오가 없습니다.")
    frame = holdings.copy()
    values = pd.to_numeric(frame["market_value"], errors="coerce").fillna(0).clip(lower=0)
    total = float(values.sum())
    if total <= 0:
        raise ValueError("포트폴리오 평가금액이 0보다 커야 합니다.")
    weights = values / total
    normalized_symbols = frame["symbol"].astype(str).str.upper()
    weight_by_symbol = weights.groupby(normalized_symbols).sum()
    ordered = weight_by_symbol.sort_values(ascending=False)
    hhi = float((weight_by_symbol**2).sum())
    leverage_source = (
        frame["leverage_factor"]
        if "leverage_factor" in frame
        else pd.Series(1, index=frame.index)
    )
    leverage = pd.to_numeric(leverage_source, errors="coerce").fillna(1)
    leveraged_weight = float(weights[leverage.abs() > 1.05].sum())
    currency = frame.get("currency", pd.Series("KRW", index=frame.index)).astype(str).str.upper()
    foreign_weight = float(weights[currency.ne("KRW")].sum())

    returns: dict[str, pd.Series] = {}
    symbol_weights: dict[str, float] = {}
    for index, holding in frame.iterrows():
        symbol = str(holding["symbol"]).upper()
        candles = daily_candles.get(symbol)
        if candles is None or candles.empty or "close_price" not in candles:
            continue
        close = pd.to_numeric(candles["close_price"], errors="coerce")
        timestamps = pd.to_datetime(candles["timestamp"], utc=True, errors="coerce")
        series = pd.Series(close.to_numpy(), index=timestamps).dropna().sort_index()
        series = series[~series.index.duplicated(keep="last")].pct_change(fill_method=None).dropna()
        if not series.empty:
            returns[symbol] = series
            symbol_weights[symbol] = symbol_weights.get(symbol, 0) + float(weights.loc[index])

    portfolio_returns = pd.Series(dtype=float)
    if returns:
        matrix = pd.concat(returns, axis=1, sort=False).dropna()
        covered_weight = sum(symbol_weights[symbol] for symbol in matrix.columns)
        if covered_weight > 0:
            normalized = pd.Series({symbol: symbol_weights[symbol] / covered_weight for symbol in matrix.columns})
            portfolio_returns = matrix.mul(normalized, axis=1).sum(axis=1)

    volatility = drawdown = var95 = None
    if len(portfolio_returns) >= 20:
        volatility = float(portfolio_returns.std(ddof=1) * math.sqrt(252) * 100)
        wealth = (1 + portfolio_returns).cumprod()
        drawdown = float(((wealth / wealth.cummax()) - 1).min() * 100)
        var95 = float(max(0, -portfolio_returns.quantile(0.05) * 100))

    concentration_points = min(30, float(ordered.iloc[0]) * 22 + hhi * 18)
    volatility_points = min(30, (volatility or 0) / 60 * 30)
    drawdown_points = min(20, abs(drawdown or 0) / 60 * 20)
    leverage_points = leveraged_weight * 20
    score = round(min(100, concentration_points + volatility_points + drawdown_points + leverage_points))
    level = "안정 성향 관찰" if score <= 33 else "중립 성향 관찰" if score <= 66 else "공격 성향 관찰"
    price_coverage = sum(symbol_weights.values())
    confidence = round(min(100, 35 + price_coverage * 45 + min(len(portfolio_returns), 252) / 252 * 20))

    reasons = [
        f"최대 보유 종목 비중 {ordered.iloc[0] * 100:.1f}%",
        f"상위 3개 종목 비중 {ordered.head(3).sum() * 100:.1f}%",
        f"집중도 HHI {hhi:.3f} (유효 종목 수 {1 / hhi:.1f}개)",
        f"레버리지·인버스 추정 노출 {leveraged_weight * 100:.1f}%",
    ]
    if volatility is not None:
        reasons.extend([
            f"최근 저장 일봉 기준 연환산 변동성 {volatility:.1f}%",
            f"동일 구간 최대 낙폭 {drawdown:.1f}%",
            f"일간 역사적 VaR 95% {var95:.1f}%",
        ])
    else:
        reasons.append("공통 일봉 표본이 20개 미만이라 변동성·낙폭·VaR를 계산하지 않음")

    features = PortfolioRiskFeatures(
        holdings_count=int(len(weight_by_symbol)), total_market_value=_round(total),
        top1_weight_pct=_round(ordered.iloc[0] * 100),
        top3_weight_pct=_round(ordered.head(3).sum() * 100),
        concentration_hhi=_round(hhi, 4), effective_holdings=_round(1 / hhi),
        leveraged_weight_pct=_round(leveraged_weight * 100),
        foreign_currency_weight_pct=_round(foreign_weight * 100),
        return_observations=int(len(portfolio_returns)),
        annualized_volatility_pct=None if volatility is None else _round(volatility),
        maximum_drawdown_pct=None if drawdown is None else _round(drawdown),
        historical_var_95_pct=None if var95 is None else _round(var95),
    )
    return ObservedRiskProfile(
        score=score, level=level, confidence=confidence, features=features,
        reasons=tuple(reasons),
        missing_information=(
            "투자 목적", "투자 기간", "소득·순자산·부채", "생활자금 의존도",
            "필요 유동성", "감내 가능한 손실", "투자 경험", "다른 금융자산",
        ),
    )


def build_llm_risk_context(profile: ObservedRiskProfile) -> dict[str, Any]:
    """Create a deterministic, non-PII context; no LLM is called here."""
    features = asdict(profile.features)
    features.pop("total_market_value", None)
    return {
        "schema_version": "porto.observed-risk.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": "observed_portfolio_risk_not_investor_suitability",
        "classification": {
            "score_0_100": profile.score,
            "label": profile.level,
            "confidence_0_100": profile.confidence,
        },
        "features": features,
        "evidence": list(profile.reasons),
        "unknown_user_factors": list(profile.missing_information),
        "llm_guardrails": [
            "Do not present this as a legally valid investor suitability assessment.",
            "Do not recommend a specific buy, sell, or guaranteed return.",
            "Clearly separate observed portfolio risk from willingness and capacity to take risk.",
            "Mention missing user factors and data limitations in the answer.",
        ],
    }
