"""Porto Manager analysis dialog."""

import pandas as pd
import streamlit as st

from toss_manager.analysis import analyze_candles


@st.dialog("Porto 매니저 분석", width="large")
def show_manager_dialog(name: str, symbol: str, candles: pd.DataFrame) -> None:
    st.markdown(f"### {name}")
    st.caption(f"{symbol} · 일봉 기술적 분석 · 투자 권유가 아닌 과거 패턴 참고 정보입니다.")
    try:
        result = analyze_candles(candles)
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
    c2.metric("다음 캔들 상승", f"{stats.rises:,}회")
    c3.metric("다음 캔들 하락", f"{stats.falls:,}회")
    if stats.rise_rate is None:
        st.info("비교할 수 있는 과거 신호가 없습니다.")
    else:
        base_delta = stats.rise_rate - (stats.base_rise_rate or 0)
        st.metric("과거 상승 비율", f"{stats.rise_rate:.1f}%", f"전체 기준 대비 {base_delta:+.1f}%p")
        st.caption(f"보합 {stats.flats:,}회 · 다음 일봉 수익률 ±0.2% 이내를 보합으로 분류")

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
    st.caption(f"분석 캔들 {result.candle_count:,}개 · 기준 시각 {result.analyzed_at}")
