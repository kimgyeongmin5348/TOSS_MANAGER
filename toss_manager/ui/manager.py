"""Porto Manager analysis dialog."""

import pandas as pd
import streamlit as st
from sqlalchemy import Engine
from sqlalchemy.exc import SQLAlchemyError

from toss_manager.analysis import analyze_candles
from toss_manager.news import sync_symbol_news
from toss_manager.news.models import NewsSyncResult


@st.fragment(run_every="60s")
def render_manager_launcher(
    engine: Engine,
    *,
    name: str,
    symbol: str,
    market_country: str,
    candles: pd.DataFrame,
    period: str,
    return_threshold: float,
    offline: bool = False,
) -> None:
    """Refresh news every minute while the stock detail remains open."""
    try:
        news_result = sync_symbol_news(
            engine,
            symbol=symbol,
            name=name,
            market_country=market_country,
            period=period,
        )
    except (SQLAlchemyError, ValueError):
        news_result = None
    prefix = "저장 데이터로 " if offline else ""
    if st.button(
        f"✨ {prefix}Porto 매니저 분석 · 다음 {period}봉",
        use_container_width=True,
        key=f"manager_{'offline' if offline else 'live'}_{market_country}_{symbol}_{period}",
    ):
        show_manager_dialog(
            name,
            symbol,
            candles,
            period=period,
            return_threshold=return_threshold,
            news_result=news_result,
        )


@st.dialog("Porto 매니저 분석", width="small")
def show_manager_dialog(
    name: str,
    symbol: str,
    candles: pd.DataFrame,
    period: str = "1일",
    return_threshold: float = 0.002,
    news_result: NewsSyncResult | None = None,
) -> None:
    candle_label = f"{period}봉"
    st.markdown(f"### {name}")
    st.caption(
        f"{symbol} · {candle_label} 기술적 분석 · "
        f"예측 대상: 다음 {candle_label} 종가 방향"
    )
    st.caption("투자 권유가 아닌 과거 패턴 참고 정보입니다.")
    try:
        result = analyze_candles(candles, return_threshold=return_threshold)
    except ValueError as exc:
        st.warning(str(exc))
        return

    st.markdown("**현재 분석 점수**")
    st.progress(result.score / 100, text=f"{result.score} / 100")
    direction_icon = "▲" if result.direction == "상승 우세" else "▼" if result.direction == "하락 우세" else "━"
    direction_tone = "manager-up" if result.direction == "상승 우세" else "manager-down" if result.direction == "하락 우세" else "manager-flat"
    st.markdown(f'<div class="manager-direction {direction_tone}"><small>예상 방향</small><b>{direction_icon} {result.direction}</b></div>', unsafe_allow_html=True)

    stats = result.backtest
    c1, c2, c3 = st.columns(3)
    c1.metric(f"과거 {stats.match_type} 신호", f"{stats.occurrences:,}회")
    c2.metric(f"다음 {candle_label} 상승", f"{stats.rises:,}회")
    c3.metric(f"다음 {candle_label} 하락", f"{stats.falls:,}회")
    if stats.rise_rate is None:
        st.info("비교할 수 있는 과거 신호가 없습니다.")
    else:
        base_delta = stats.rise_rate - (stats.base_rise_rate or 0)
        st.metric("과거 상승 비율", f"{stats.rise_rate:.1f}%", f"전체 기준 대비 {base_delta:+.1f}%p")
        threshold_percent = return_threshold * 100
        st.caption(
            f"보합 {stats.flats:,}회 · 다음 {candle_label} 종가 수익률 "
            f"±{threshold_percent:g}% 이내를 보합으로 분류"
        )

    st.markdown("#### 주요 근거")
    for evidence in result.evidence:
        icon = "▲" if evidence.state > 0 else "▼" if evidence.state < 0 else "━"
        tone = "manager-up" if evidence.state > 0 else "manager-down" if evidence.state < 0 else "manager-flat"
        st.markdown(
            f'<div class="manager-evidence"><b>{evidence.label}</b>'
            f'<span class="{tone}">{icon} {evidence.description}</span>'
            f'<small>{evidence.points:g} / {evidence.maximum:g}</small></div>',
            unsafe_allow_html=True,
        )

    st.markdown("#### 뉴스 신호")
    if news_result is None:
        st.caption("뉴스 저장소를 확인하지 못해 기술적 분석만 표시합니다.")
    elif not news_result.active_providers and news_result.summary.article_count == 0:
        st.caption("뉴스 API가 설정되지 않아 기술적 분석만 표시합니다.")
    else:
        news = news_result.summary
        tone = (
            "manager-up" if news.direction == "긍정"
            else "manager-down" if news.direction == "부정"
            else "manager-flat"
        )
        st.markdown(
            f'<div class="manager-direction {tone}"><small>뉴스 심리</small>'
            f'<b>{news.direction} {news.score}점</b></div>',
            unsafe_allow_html=True,
        )
        provider_label = ", ".join(news_result.active_providers) or "저장 데이터"
        st.caption(
            f"관련 뉴스·공시 {news.article_count}건 · 신뢰도 {news.confidence}점 · "
            f"공급자 {provider_label}"
        )
        st.caption(
            f"긍정 {news.positive_count}건 · 중립 {news.neutral_count}건 · "
            f"부정 {news.negative_count}건 · 관련성 부족 제외 {news.excluded_count}건"
        )
        st.caption(
            f"평균 종목 관련도 {news.average_relevance}% · "
            f"기사 간 방향 일치도 {news.agreement}%"
        )
        for reason in news.reasons:
            st.caption(f"• {reason}")
        with st.expander("뉴스 점수 산정 기준", expanded=False):
            for explanation in news.methodology:
                st.caption(f"• {explanation}")
        if news_result.errors:
            st.caption("일부 뉴스 공급자의 최신 조회에 실패해 저장 데이터로 분석했습니다.")
    st.caption(f"분석 캔들 {result.candle_count:,}개 · 기준 시각 {result.analyzed_at}")
