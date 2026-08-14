"""Market ranking and stock chart views."""

import re
from datetime import datetime, timedelta, timezone

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from sqlalchemy import Engine
from sqlalchemy.exc import SQLAlchemyError

from toss_manager.client import TossAPIClient, TossAPIError
from toss_manager.transform import candles_frame
from toss_manager.repository import candle_coverage, load_candles, upsert_candles

from .common import PERIODS, aggregate_candles, currency, percentage, percentage_text
from .manager import render_manager_launcher


INTRADAY_RAW_COUNTS = {"1분": 200, "5분": 1_000, "10분": 2_000}
RETURN_THRESHOLDS = {
    "1분": 0.0005,
    "5분": 0.001,
    "10분": 0.0015,
    "1일": 0.002,
    "주": 0.005,
    "월": 0.01,
    "년": 0.02,
}


def render_stock_detail(
    client: TossAPIClient,
    symbol: str,
    market: str,
    holdings: pd.DataFrame,
    engine: Engine,
    name: str | None = None,
) -> None:
    try:
        stock_info = client.get_stocks([symbol])
        stock_info = stock_info[0] if stock_info else {}
        name = stock_info.get("name") or name or symbol
        prices = client.get_prices([symbol])
        price = prices[0] if prices else {}
    except TossAPIError as exc:
        st.error(f"종목 정보를 불러오지 못했습니다: {exc}")
        return

    last_price = float(price.get("lastPrice") or 0)
    market_name = "미국" if market == "US" else "한국"
    st.markdown(
        f'<div class="card"><div class="stock-head"><div><h2>{name}</h2>'
        f'<div class="caption">{symbol} · {market_name}</div></div><div>'
        f'<div class="price">{currency(last_price, market)}</div>'
        '<div class="caption">현재가</div></div></div></div>',
        unsafe_allow_html=True,
    )
    st.write("")
    try:
        with st.spinner("최근 5년 일봉을 확인하고 저장하고 있습니다..."):
            daily_frame = sync_daily_candles(
                client, engine, symbol, market, stock_info
            )
    except (SQLAlchemyError, TossAPIError, ValueError) as exc:
        st.error(f"장기 캔들 동기화 또는 조회에 실패했습니다: {exc}")
        return

    period = st.segmented_control("캔들 주기", list(PERIODS), default="1일")
    period = period or "1일"
    api_interval, rule, count = PERIODS[period]
    try:
        if api_interval == "1d":
            raw_frame = daily_frame
        else:
            payload = client.get_candle_window(
                symbol,
                interval=api_interval,
                target_count=INTRADAY_RAW_COUNTS.get(period, count),
            )
            raw_frame = candles_frame(payload, symbol, api_interval)
            try:
                upsert_candles(
                    engine, symbol=symbol, market_country=market,
                    stock=stock_info, candles=raw_frame, adjusted=True,
                )
            except SQLAlchemyError:
                st.warning("캔들 저장에 실패했지만 최신 차트는 계속 표시합니다.")
        frame = aggregate_candles(raw_frame, rule)
        if frame.empty:
            st.info("표시할 차트 데이터가 없습니다.")
            return
        render_manager_launcher(
            engine,
            name=name,
            symbol=symbol,
            market_country=market,
            candles=frame,
            period=period,
            return_threshold=RETURN_THRESHOLDS[period],
        )
        figure = build_candlestick_figure(frame, symbol, market, holdings)
        st.plotly_chart(
            figure,
            use_container_width=True,
            config={"displayModeBar": False, "scrollZoom": True},
        )
        st.caption(
            "마우스 왼쪽 버튼을 누른 채 좌우로 끌어 시점을 이동하고, "
            "휠로 확대·축소할 수 있습니다."
        )
        if period in {"5분", "10분", "주", "월", "년"}:
            st.caption(f"공식 {api_interval} 데이터를 {period} 단위로 집계한 차트입니다.")
    except (TossAPIError, ValueError) as exc:
        st.error(f"차트 데이터를 불러오지 못했습니다: {exc}")
    except SQLAlchemyError:
        st.error("장기 캔들 동기화 또는 조회에 실패했습니다.")


def sync_daily_candles(
    client: TossAPIClient,
    engine: Engine,
    symbol: str,
    market: str,
    stock_info: dict,
) -> pd.DataFrame:
    """Initial five-year backfill, then incremental refresh from the DB boundary."""
    coverage = candle_coverage(
        engine, symbol=symbol, market_country=market, interval="1d"
    )
    first = coverage["first_at"]
    latest = coverage["last_at"]
    cutoff = datetime.now(timezone.utc) - timedelta(days=round(5 * 365.25))
    first_utc = None
    if first is not None:
        first_utc = (
            first.replace(tzinfo=timezone.utc)
            if first.tzinfo is None
            else first.astimezone(timezone.utc)
        )
    if first_utc is None or first_utc > cutoff + timedelta(days=7):
        payload = client.get_candle_history(symbol, interval="1d", years=5)
    else:
        payload = client.get_candles_since(symbol, since=latest, interval="1d")
    incoming = candles_frame(payload, symbol, "1d")
    upsert_candles(
        engine, symbol=symbol, market_country=market,
        stock=stock_info, candles=incoming, adjusted=True,
    )
    stored = load_candles(
        engine, symbol=symbol, market_country=market, interval="1d"
    )
    frame = pd.DataFrame(stored)
    if frame.empty:
        return incoming
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
    for column in ["open_price", "high_price", "low_price", "close_price", "volume"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame


def build_candlestick_figure(
    frame: pd.DataFrame, symbol: str, market: str, holdings: pd.DataFrame
) -> go.Figure:
    figure = go.Figure(
        go.Candlestick(
            x=frame.timestamp,
            open=frame.open_price,
            high=frame.high_price,
            low=frame.low_price,
            close=frame.close_price,
            increasing_line_color="#e5484d",
            increasing_fillcolor="#e5484d",
            decreasing_line_color="#2864dc",
            decreasing_fillcolor="#2864dc",
            name=symbol,
        )
    )
    owned = (
        holdings[holdings["symbol"].astype(str).str.upper().eq(symbol.upper())]
        if not holdings.empty and "symbol" in holdings
        else pd.DataFrame()
    )
    if not owned.empty:
        average_price = pd.to_numeric(
            owned.iloc[0].get("average_purchase_price"), errors="coerce"
        )
        if pd.notna(average_price) and float(average_price) > 0:
            average_price = float(average_price)
            figure.add_hline(
                y=average_price,
                line_color="#7c3aed",
                line_width=1.5,
                line_dash="dash",
                annotation_text=f"내 평균 단가 {currency(average_price, market)}",
                annotation_position="top left",
                annotation_font_color="#7c3aed",
                annotation_bgcolor="rgba(255,255,255,.9)",
            )
    figure.update_layout(
        height=560,
        dragmode="pan",
        hovermode="x unified",
        margin=dict(l=10, r=10, t=25, b=10),
        xaxis_rangeslider_visible=False,
        paper_bgcolor="white",
        plot_bgcolor="white",
        yaxis=dict(
            side="right",
            gridcolor="#eef0f4",
            tickprefix="$" if market == "US" else "₩",
        ),
        xaxis=dict(gridcolor="#f3f4f6", fixedrange=False),
        showlegend=False,
    )
    return figure


def render_market_view(
    client: TossAPIClient, holdings: pd.DataFrame, engine: Engine
) -> None:
    market_label = st.segmented_control(
        "시장", ["미장", "국장"], default="미장", key="market_selector"
    )
    market = "US" if market_label == "미장" else "KR"
    st.markdown(
        f'<div class="page-head"><div><h1>{market_label} 거래량 순위</h1>'
        '<p>실시간 시장 거래량 기준 · 상위 50개 종목</p></div></div>',
        unsafe_allow_html=True,
    )
    with st.form("search", clear_on_submit=False):
        query_column, button_column = st.columns([5, 1])
        query = query_column.text_input(
            "종목 검색",
            placeholder="티커 입력 (예: AAPL, TSLA)",
            label_visibility="collapsed",
        )
        searched = button_column.form_submit_button("검색", use_container_width=True)
    if searched:
        symbol = query.strip().upper()
        if not re.fullmatch(r"[A-Z0-9.\-]+", symbol):
            st.warning("올바른 종목 티커를 입력해 주세요.")
        else:
            st.session_state.selected_symbol = symbol
            st.session_state.selected_market = market

    if (
        st.session_state.get("selected_symbol")
        and st.session_state.get("selected_market") == market
    ):
        if st.button("← 거래량 순위로 돌아가기"):
            st.session_state.pop("selected_symbol", None)
            st.rerun()
        render_stock_detail(
            client, st.session_state.selected_symbol, market, holdings, engine
        )
        return
    _render_rankings(client, market)


def _render_rankings(client: TossAPIClient, market: str) -> None:
    try:
        payload = client.get_rankings(market, count=50)
        rankings = payload.get("rankings", [])
    except (TossAPIError, ValueError) as exc:
        st.error(f"거래량 순위를 불러오지 못했습니다: {exc}")
        return
    if not rankings:
        st.markdown(
            '<div class="card empty">현재 집계된 거래량 순위가 없습니다.</div>',
            unsafe_allow_html=True,
        )
        return

    symbols = [item["symbol"] for item in rankings]
    try:
        stocks = {item["symbol"]: item for item in client.get_stocks(symbols)}
    except TossAPIError:
        stocks = {}
    st.markdown('<div class="card">', unsafe_allow_html=True)
    for item in rankings:
        _render_ranking_row(item, stocks, market)
    st.markdown("</div>", unsafe_allow_html=True)


def _render_ranking_row(item: dict, stocks: dict, market: str) -> None:
    symbol = item["symbol"]
    price = item.get("price", {})
    last_price = float(price.get("lastPrice") or 0)
    rate = percentage(price.get("changeRate"))
    volume = float(item.get("tradingVolume") or 0)
    tone = "negative" if rate < 0 else ""
    name = stocks.get(symbol, {}).get("name", symbol)
    content, action = st.columns([7, 1])
    content.markdown(
        f'<div class="rank-row"><span class="rank">{item.get("rank", "")}</span>'
        f'<span><span class="sym">{name}</span><div class="sub">{symbol}</div></span>'
        f'<span class="num">{currency(last_price, market)}</span>'
        f'<span class="num rate {tone}">{percentage_text(price.get("changeRate"))}</span>'
        f'<span class="num">{volume:,.0f}주</span></div>',
        unsafe_allow_html=True,
    )
    if action.button("보기", key=f"rank_{market}_{symbol}"):
        st.session_state.selected_symbol = symbol
        st.session_state.selected_market = market
        st.rerun()
