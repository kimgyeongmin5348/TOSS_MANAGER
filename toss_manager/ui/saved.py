"""Database-only portfolio, holdings navigation, and candle view."""

import pandas as pd
import streamlit as st
from sqlalchemy import Engine
from sqlalchemy.exc import SQLAlchemyError

from toss_manager.repository import load_saved_candles, load_saved_portfolio

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
