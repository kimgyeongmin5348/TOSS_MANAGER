"""Database-only portfolio, holdings navigation, and candle view."""

from hashlib import sha256

import pandas as pd
import streamlit as st
from sqlalchemy import Engine
from sqlalchemy.exc import SQLAlchemyError

from toss_manager.repository import load_saved_candles, load_saved_portfolio
from toss_manager.risk_profile import analyze_portfolio_risk
from toss_manager.llm import (
    NvidiaLLMClient,
    NvidiaLLMError,
    build_llm_messages,
    build_portfolio_manager_context,
)

from .common import aggregate_candles
from .formatting import currency, percentage_text
from .manager import render_manager_launcher
from .market import RETURN_THRESHOLDS, build_candlestick_figure


OFFLINE_PERIODS = {
    "1일": None,
    "주": "W-FRI",
    "월": "ME",
    "년": "YE",
}


def render_saved_view(engine: Engine, user_id: int) -> None:
    try:
        rows = load_saved_portfolio(engine, user_id)
    except SQLAlchemyError:
        st.error("저장된 포트폴리오를 불러오지 못했습니다.")
        return
    if not rows:
        st.info("저장된 보유 종목이 없습니다. 토스 실시간 연결을 먼저 진행해 주세요.")
        return

    holdings = pd.DataFrame(rows)
    _render_offline_sidebar(holdings)
    selected = st.session_state.get("offline_symbol")
    if selected:
        match = holdings[holdings["symbol"].astype(str).str.upper().eq(selected)]
        if not match.empty:
            _render_saved_stock(engine, user_id, match.iloc[0], holdings)
            return
    _render_portfolio_table(holdings)
    _render_risk_overview(engine, user_id, holdings)


def _risk_label(score: int) -> tuple[str, str, str, str]:
    if score <= 33:
        return "안정형", "#4e9b82", "#ebf8f3", "천천히 흔들림을 줄이는 편"
    if score <= 66:
        return "균형형", "#d18a3d", "#fff6e8", "안정과 수익 기회를 함께 보는 편"
    return "공격형", "#e35f69", "#fff0f1", "변동성을 감수하고 기회를 보는 편"


def _risk_ai_sentence(profile: object, holdings: pd.DataFrame, user_id: int) -> str:
    """Return one stable sentence; use the LLM only to select a constrained label."""
    fallback, _, _, _ = _risk_label(profile.score)
    client = NvidiaLLMClient()
    if not client.configured:
        return f"당신은 {fallback} 투자자입니다."

    fingerprint = sha256(
        f"risk-v1|{user_id}|{profile.score}|{profile.confidence}|{profile.features}".encode("utf-8")
    ).hexdigest()[:20]
    cache_key = f"porto_risk_line_{fingerprint}"
    if cached := st.session_state.get(cache_key):
        return str(cached)

    context = build_portfolio_manager_context(profile=profile, holdings=holdings)
    question = (
        "관찰된 포트폴리오 위험만 기준으로 안정형, 균형형, 공격형 중 하나를 고르세요. "
        "다른 설명 없이 반드시 '당신은 OOO 투자자입니다.' 한 문장만 한국어로 답하세요."
    )
    try:
        response = client.complete(build_llm_messages(context, user_question=question))
    except NvidiaLLMError:
        response = ""

    selected = next((label for label in ("안정형", "균형형", "공격형") if label in response), fallback)
    sentence = f"당신은 {selected} 투자자입니다."
    st.session_state[cache_key] = sentence
    return sentence


def _render_risk_overview(engine: Engine, user_id: int, holdings: pd.DataFrame) -> None:
    """Always-visible visual summary of observed portfolio risk."""
    try:
        candle_sets = {}
        for symbol in holdings["symbol"].astype(str).str.upper().unique():
            rows = load_saved_candles(engine, user_id=user_id, symbol=symbol, interval="1d")
            candle_sets[symbol] = pd.DataFrame(rows)
        profile = analyze_portfolio_risk(holdings, candle_sets)
    except (SQLAlchemyError, ValueError) as exc:
        st.error(f"위험도를 계산하지 못했습니다: {exc}")
        return

    label, accent, tint, description = _risk_label(profile.score)
    features = profile.features
    volatility = features.annualized_volatility_pct
    volatility_text = f"{volatility:.1f}%" if volatility is not None else "표본 부족"
    volatility_width = min(100, (volatility or 0) / 60 * 100)
    concentration_width = min(100, features.top1_weight_pct)
    leverage_width = min(100, features.leveraged_weight_pct)

    st.markdown(
        """
        <style>
        .risk-wrap{padding:20px;border:1px solid #e5e9f0;border-radius:24px;background:#fff;margin:20px 0}
        .risk-hero{display:flex;align-items:center;gap:18px;padding:17px;border-radius:19px}
        .risk-ring{width:104px;height:104px;border-radius:50%;display:grid;place-items:center;position:relative;flex:0 0 104px}
        .risk-ring:after{content:"";position:absolute;inset:10px;border-radius:50%;background:#fff}
        .risk-ring div{position:relative;z-index:1;text-align:center}.risk-ring b{display:block;font-size:1.4rem}.risk-ring small{color:#858b98}
        .risk-copy small{font-size:.72rem;font-weight:800;letter-spacing:.08em;color:#858b98}.risk-copy h3{margin:4px 0;font-size:1.45rem}
        .risk-copy p{margin:0;color:#6d7380;font-size:.78rem}.risk-ai{margin:12px 0;padding:14px 16px;border-radius:16px;
          background:linear-gradient(135deg,#f7f3ff,#f1f7ff);font-size:1rem;font-weight:900;color:#332b50}
        .risk-row{display:grid;grid-template-columns:90px 1fr 70px;align-items:center;gap:9px;margin:12px 0;font-size:.75rem;color:#5d6471}
        .risk-track{height:9px;border-radius:99px;background:#edf0f4;overflow:hidden}.risk-fill{height:100%;border-radius:99px}
        .risk-value{text-align:right;font-weight:800;color:#303543}.risk-note{font-size:.69rem;color:#858b98;line-height:1.55;margin-top:10px}
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        f"""
        <div class="risk-wrap">
          <div class="risk-hero" style="background:{tint}">
            <div class="risk-ring" style="background:conic-gradient({accent} {profile.score * 3.6}deg,#e6e9ee 0)">
              <div><b>{profile.score}</b><small>위험 점수</small></div></div>
            <div class="risk-copy"><small>PORTFOLIO RISK</small><h3 style="color:{accent}">{label}</h3><p>{description}</p></div>
          </div>
          <div class="risk-ai">✦ {_risk_ai_sentence(profile, holdings, user_id)}</div>
          <div class="risk-row"><span>종목 집중도</span><div class="risk-track"><div class="risk-fill" style="width:{concentration_width:.1f}%;background:#d58a47"></div></div><span class="risk-value">{features.top1_weight_pct:.1f}%</span></div>
          <div class="risk-row"><span>연 변동성</span><div class="risk-track"><div class="risk-fill" style="width:{volatility_width:.1f}%;background:#e06a73"></div></div><span class="risk-value">{volatility_text}</span></div>
          <div class="risk-row"><span>레버리지</span><div class="risk-track"><div class="risk-fill" style="width:{leverage_width:.1f}%;background:#7f77c8"></div></div><span class="risk-value">{features.leveraged_weight_pct:.1f}%</span></div>
          <div class="risk-note">데이터 신뢰도 {profile.confidence}/100 · 보유 {features.holdings_count}종목 · 이 결과는 현재 보유 구성에서 관찰된 위험이며 법적 투자성향 진단이 아닙니다.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_risk_context(engine: Engine, user_id: int, holdings: pd.DataFrame) -> None:
    st.markdown("### 관찰 포트폴리오 위험도")
    st.caption(
        "보유 구성과 저장 일봉에서 계산한 객관적 위험 특성입니다. "
        "사용자의 법적 투자성향 또는 적합성 판정이 아닙니다."
    )
    if not st.button("위험 특성 계산", use_container_width=True):
        return
    try:
        candle_sets = {}
        for symbol in holdings["symbol"].astype(str).str.upper().unique():
            rows = load_saved_candles(engine, user_id=user_id, symbol=symbol, interval="1d")
            candle_sets[symbol] = pd.DataFrame(rows)
        profile = analyze_portfolio_risk(holdings, candle_sets)
    except (SQLAlchemyError, ValueError) as exc:
        st.error(f"위험 특성을 계산하지 못했습니다: {exc}")
        return
    st.metric("관찰 위험 점수", f"{profile.score} / 100", profile.level)
    st.progress(profile.confidence / 100, text=f"데이터 신뢰도 {profile.confidence} / 100")
    for reason in profile.reasons:
        st.caption(f"• {reason}")
    st.warning(
        "투자 목적, 기간, 재무상황, 생활자금 의존도와 손실 감내 수준은 "
        "포트폴리오 데이터만으로 알 수 없어 별도 질문이 필요합니다."
    )


def _render_offline_sidebar(holdings: pd.DataFrame) -> None:
    st.sidebar.markdown('<div class="brand"><span class="mark">P</span>porto</div>', unsafe_allow_html=True)
    st.sidebar.caption("● 저장 데이터 모드")
    st.sidebar.markdown('<div class="side-title">SAVED HOLDINGS</div>', unsafe_allow_html=True)
    for holding in holdings.drop_duplicates("symbol").itertuples():
        market = "US" if holding.currency == "USD" else "KR"
        if st.sidebar.button(
            f"**{holding.name or holding.symbol}**　{percentage_text(holding.profit_loss_rate)}  \n"
            f"{holding.symbol} · 평단 {currency(float(holding.average_purchase_price or 0), market)}",
            key=f"offline_{holding.symbol}", use_container_width=True,
        ):
            st.session_state.offline_symbol = str(holding.symbol).upper()
            st.rerun()


def _render_portfolio_table(holdings: pd.DataFrame) -> None:
    st.subheader("저장된 포트폴리오")
    latest = pd.to_datetime(holdings["captured_at"]).max()
    st.caption(f"마지막 저장 시각(UTC): {latest} · 실시간 가격이 아닙니다.")
    for account, items in holdings.groupby(["account_no_masked", "account_type"], dropna=False):
        st.markdown(f"#### {account[0]} · {account[1] or '계좌'}")
        display = items.copy()
        display["저장 가격"] = display.apply(lambda row: currency(float(row["last_price"] or 0), "US" if row["currency"] == "USD" else "KR"), axis=1)
        display["평균 단가"] = display.apply(lambda row: currency(float(row["average_purchase_price"] or 0), "US" if row["currency"] == "USD" else "KR"), axis=1)
        display["수익률"] = display["profit_loss_rate"].apply(percentage_text)
        table = display[["name", "symbol", "quantity", "저장 가격", "평균 단가", "수익률"]].rename(
            columns={"name": "종목", "symbol": "심볼", "quantity": "수량"}
        ).style.map(
            lambda value: "color:#e5484d;font-weight:600" if str(value).startswith("+") and value != "+0.00%"
            else "color:#2864dc;font-weight:600" if str(value).startswith("-") else "",
            subset=["수익률"],
        )
        st.dataframe(table, use_container_width=True, hide_index=True)


def _render_saved_stock(
    engine: Engine, user_id: int, holding: pd.Series, holdings: pd.DataFrame
) -> None:
    symbol = str(holding["symbol"]).upper()
    name = holding.get("name") or symbol
    market = "US" if holding.get("currency") == "USD" else "KR"
    if st.button("← 저장된 포트폴리오로 돌아가기"):
        st.session_state.pop("offline_symbol", None)
        st.rerun()
    st.markdown(
        f'<div class="card"><div class="stock-head"><div><h2>{name}</h2>'
        f'<div class="caption">{symbol} · 저장 데이터</div></div><div>'
        f'<div class="price">{currency(float(holding.get("last_price") or 0), market)}</div>'
        f'<div class="caption">{holding.get("captured_at")} UTC 기준</div></div></div></div>',
        unsafe_allow_html=True,
    )
    try:
        rows = load_saved_candles(engine, user_id=user_id, symbol=symbol, interval="1d")
    except SQLAlchemyError:
        st.error("저장된 캔들을 불러오지 못했습니다.")
        return
    if not rows:
        st.info("이 종목의 저장된 일봉이 없습니다. 실시간 연결 후 매니저 분석을 실행해 주세요.")
        return
    candles = pd.DataFrame(rows)
    candles["timestamp"] = pd.to_datetime(candles["timestamp"], utc=True)
    for column in ["open_price", "high_price", "low_price", "close_price", "volume"]:
        candles[column] = pd.to_numeric(candles[column], errors="coerce")
    period = st.segmented_control("저장 캔들 주기", list(OFFLINE_PERIODS), default="1일")
    period = period or "1일"
    chart = aggregate_candles(candles, OFFLINE_PERIODS[period])
    render_manager_launcher(
        engine,
        name=name,
        symbol=symbol,
        market_country=market,
        candles=chart,
        period=period,
        return_threshold=RETURN_THRESHOLDS[period],
        offline=True,
    )
    figure = build_candlestick_figure(chart, symbol, market, holdings)
    st.plotly_chart(figure, use_container_width=True, config={"displayModeBar": False, "scrollZoom": True})
    st.caption("DB에 저장된 일봉입니다. 좌우 드래그로 이동하고 휠로 확대·축소할 수 있습니다.")
