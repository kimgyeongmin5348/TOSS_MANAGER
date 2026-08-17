"""Portfolio-first home and holdings views shared by live and saved modes."""

from __future__ import annotations

import html
from typing import Any

import pandas as pd
import plotly.express as px
import streamlit as st

from .formatting import currency, percentage_text


NUMERIC_COLUMNS = (
    "quantity", "purchase_amount", "market_value", "profit_loss",
    "profit_loss_rate", "daily_profit_loss", "daily_profit_loss_rate",
)


def _prepared(holdings: pd.DataFrame) -> pd.DataFrame:
    frame = holdings.copy()
    for column in NUMERIC_COLUMNS:
        if column not in frame:
            frame[column] = 0.0
        frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0.0)
    if "currency" not in frame:
        frame["currency"] = "KRW"
    frame["currency"] = frame["currency"].fillna("KRW").astype(str).str.upper()
    if "name" not in frame:
        frame["name"] = frame.get("symbol", "-")
    return frame


def _timestamp(holdings: pd.DataFrame) -> str:
    if "captured_at" not in holdings or holdings.empty:
        return "기준 시각 없음"
    value = pd.to_datetime(holdings["captured_at"], errors="coerce", utc=True).max()
    if pd.isna(value):
        return "기준 시각 없음"
    return value.tz_convert("Asia/Seoul").strftime("%Y.%m.%d %H:%M KST")


def _totals(frame: pd.DataFrame, column: str) -> dict[str, float]:
    return {
        currency_code: float(items[column].sum())
        for currency_code, items in frame.groupby("currency")
    }


def _amount_lines(values: dict[str, float]) -> str:
    if not values:
        return "-"
    order = sorted(values, key=lambda item: (item != "KRW", item))
    return " / ".join(currency(values[item], "US" if item == "USD" else "KR") for item in order)


def _value_tone(values: dict[str, float]) -> str:
    numbers = list(values.values())
    if numbers and all(value >= 0 for value in numbers) and any(value > 0 for value in numbers):
        return "positive"
    if numbers and all(value <= 0 for value in numbers) and any(value < 0 for value in numbers):
        return "negative"
    return "neutral"


def _render_home_hero(*, name: str, live: bool, timestamp: str) -> None:
    mode = "실시간으로 보고 있어요" if live else "마지막 저장 기록이에요"
    mode_class = "live" if live else "saved"
    st.markdown(
        f"""
        <section class="home-hero">
          <div class="home-orb one"></div><div class="home-orb two"></div>
          <div class="home-hero-copy">
            <small>MY PORTFOLIO</small>
            <h1>반가워요, <em>{html.escape(name)}</em>님</h1>
            <p>오늘도 내 자산의 흐름을 편안하게 살펴봐요.</p>
          </div>
          <div class="home-mode {mode_class}">
            <b><i></i>{mode}</b><span>{html.escape(timestamp)}</span>
          </div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def _render_home_metrics(
    market_values: dict[str, float],
    purchase_values: dict[str, float],
    profit_values: dict[str, float],
    daily_values: dict[str, float],
) -> None:
    cards = (
        ("asset", "◇", "전체 평가금액", _amount_lines(market_values), "현재 보유 자산"),
        ("purchase", "⌁", "총 매입금액", _amount_lines(purchase_values), "투자한 원금"),
        ("profit", "↗", "전체 평가손익", _amount_lines(profit_values), "누적 손익"),
        ("daily", "☀", "오늘 손익", _amount_lines(daily_values), "오늘의 움직임"),
    )
    markup = []
    tones = ("neutral", "neutral", _value_tone(profit_values), _value_tone(daily_values))
    for card, tone in zip(cards, tones):
        style, icon, label, value, note = card
        markup.append(
            f'<div class="home-metric {style} {tone}"><div class="home-metric-icon">{icon}</div>'
            f'<span>{html.escape(label)}</span><b>{html.escape(value)}</b>'
            f'<small>{html.escape(note)}</small></div>'
        )
    st.markdown(
        '<div class="home-metric-grid">' + "".join(markup) + "</div>",
        unsafe_allow_html=True,
    )


def _page_header(title: str, description: str, *, live: bool, timestamp: str) -> None:
    mode = "실시간 조회" if live else "저장 데이터"
    mode_class = "live" if live else "saved"
    st.markdown(
        f'<div class="portfolio-head"><div><h1>{html.escape(title)}</h1>'
        f'<p>{html.escape(description)}</p></div><div class="data-status {mode_class}">'
        f'<b>{mode}</b><span>{html.escape(timestamp)}</span></div></div>',
        unsafe_allow_html=True,
    )


def render_home(
    holdings: pd.DataFrame,
    *,
    display_name: str | None,
    live: bool,
    history: list[dict[str, Any]] | None = None,
) -> None:
    frame = _prepared(holdings)
    name = display_name or "투자자"
    _render_home_hero(name=name, live=live, timestamp=_timestamp(frame))
    if frame.empty:
        st.info("표시할 보유 종목이 없습니다. 토스 계좌를 연결하거나 보유 내역을 확인해 주세요.")
        return

    market_values = _totals(frame, "market_value")
    purchase_values = _totals(frame, "purchase_amount")
    profit_values = _totals(frame, "profit_loss")
    daily_values = _totals(frame, "daily_profit_loss")
    _render_home_metrics(
        market_values, purchase_values, profit_values, daily_values
    )

    left, right = st.columns([1.25, 0.75], gap="large")
    with left:
        st.markdown(
            '<div class="home-section-head"><div><small>HOLDINGS</small>'
            '<h3>비중이 큰 자산</h3></div><span>상위 5개</span></div>',
            unsafe_allow_html=True,
        )
        ranked = frame.sort_values("market_value", ascending=False).head(5).copy()
        for rank, row in enumerate(ranked.itertuples(), start=1):
            market = "US" if row.currency == "USD" else "KR"
            safe_name = html.escape(str(row.name or row.symbol))
            st.markdown(
                f'<div class="holding-rank"><i>{rank:02d}</i><div><b>{safe_name}</b><span>{html.escape(str(row.symbol))}'
                f' · {html.escape(str(row.currency))}</span></div><div><b>{currency(float(row.market_value), market)}</b>'
                f'<span>{percentage_text(row.profit_loss_rate)}</span></div></div>',
                unsafe_allow_html=True,
            )
    with right:
        st.markdown(
            '<div class="home-section-head"><div><small>AT A GLANCE</small>'
            '<h3>포트폴리오 한눈에</h3></div></div>',
            unsafe_allow_html=True,
        )
        unique_count = frame["symbol"].astype(str).str.upper().nunique()
        concentration = 0.0
        if float(frame["market_value"].clip(lower=0).sum()) > 0:
            by_symbol = frame.groupby(frame["symbol"].astype(str).str.upper())["market_value"].sum()
            concentration = float(by_symbol.max() / by_symbol.sum() * 100)
        risk_label = "집중도 낮음" if concentration < 25 else "집중도 보통" if concentration < 45 else "집중도 높음"
        gauge = max(0, min(100, concentration))
        st.markdown(
            f'<div class="home-summary-card"><div class="home-gauge" '
            f'style="background:conic-gradient(#7c6ee6 {gauge * 3.6:.1f}deg,#ebe9fb 0)">'
            f'<div><b>{concentration:.1f}%</b><span>최대 비중</span></div></div>'
            f'<div class="home-summary-list"><div><span>함께 담은 종목</span><b>{unique_count}개</b></div>'
            f'<div><span>현재 구성</span><b>{risk_label}</b></div>'
            f'<small>한 종목에 치우치지 않았는지 가볍게 확인해 보세요.</small></div></div>',
            unsafe_allow_html=True,
        )

    st.markdown(
        '<div class="home-section-head wide"><div><small>CURRENCY</small>'
        '<h3>통화별로 나눠보기</h3></div></div>',
        unsafe_allow_html=True,
    )
    allocation = frame.groupby("currency", as_index=False)["market_value"].sum()
    currency_cards = []
    for row in allocation.itertuples():
        market = "US" if row.currency == "USD" else "KR"
        currency_cards.append(
            f'<div class="home-currency-card"><span>{html.escape(str(row.currency))} ASSETS</span>'
            f'<b>{html.escape(currency(float(row.market_value), market))}</b>'
            f'<small>{"달러" if row.currency == "USD" else "원화"} 자산 평가금액</small></div>'
        )
    st.markdown(
        '<div class="home-currency-grid">' + "".join(currency_cards) + "</div>",
        unsafe_allow_html=True,
    )
    st.caption("서로 다른 통화는 환율 없이 합산하거나 비중으로 환산하지 않았습니다.")

    st.markdown(
        '<div class="home-section-head wide"><div><small>RECENT CHANGE</small>'
        '<h3>최근 기록과 비교했어요</h3></div></div>',
        unsafe_allow_html=True,
    )
    history_frame = pd.DataFrame(history or [])
    if len(history_frame) < 2:
        st.markdown(
            '<div class="home-empty-note"><span>✦</span><div><b>변화를 알아보는 중이에요</b>'
            '<small>스냅샷이 두 번 이상 쌓이면 최근 자산 변화를 보여드릴게요.</small></div></div>',
            unsafe_allow_html=True,
        )
    else:
        history_frame["captured_at"] = pd.to_datetime(
            history_frame["captured_at"], errors="coerce", utc=True
        )
        history_frame = history_frame.dropna(subset=["captured_at"]).sort_values("captured_at")
        recent, previous = history_frame.iloc[-1], history_frame.iloc[-2]
        change_cards = []
        for code, market in (("krw", "KR"), ("usd", "US")):
            key = f"market_value_{code}"
            current = float(recent.get(key) or 0)
            before = float(previous.get(key) or 0)
            difference = current - before
            tone = "positive" if difference > 0 else "negative" if difference < 0 else "neutral"
            change_cards.append(
                f'<div class="home-change-card {tone}"><span>{code.upper()} 평가금액</span>'
                f'<b>{html.escape(currency(current, market))}</b>'
                f'<small>이전 기록보다 {html.escape(currency(difference, market))}</small></div>'
            )
        st.markdown(
            '<div class="home-change-grid">' + "".join(change_cards) + "</div>",
            unsafe_allow_html=True,
        )
        st.caption("최근 두 저장 시점의 평가금액 차이이며 입출금 영향을 제거한 투자수익률은 아닙니다.")


def render_portfolio(holdings: pd.DataFrame, *, live: bool) -> None:
    frame = _prepared(holdings)
    _page_header(
        "포트폴리오",
        "계좌별 보유 내역과 종목별 자산배분을 확인하세요.",
        live=live,
        timestamp=_timestamp(frame),
    )
    if frame.empty:
        st.info("표시할 포트폴리오가 없습니다.")
        return

    account_column = "account_no_masked" if "account_no_masked" in frame else "account_seq"
    labels: dict[str, Any] = {"전체 계좌": None}
    for value in frame[account_column].dropna().unique():
        labels[str(value)] = value
    selected_label = st.segmented_control("계좌 범위", list(labels), default="전체 계좌")
    selected_value = labels.get(selected_label or "전체 계좌")
    scoped = frame if selected_value is None else frame[frame[account_column].eq(selected_value)].copy()

    tab_table, tab_allocation = st.tabs(["보유 종목", "자산배분"])
    with tab_table:
        display = scoped.copy()
        total_by_currency = display.groupby("currency")["market_value"].transform("sum").replace(0, pd.NA)
        display["비중"] = (display["market_value"] / total_by_currency * 100).fillna(0).map(lambda v: f"{v:.1f}%")
        display["평가금액"] = display.apply(
            lambda row: currency(row["market_value"], "US" if row["currency"] == "USD" else "KR"), axis=1
        )
        display["평가손익"] = display.apply(
            lambda row: currency(row["profit_loss"], "US" if row["currency"] == "USD" else "KR"), axis=1
        )
        display["수익률"] = display["profit_loss_rate"].map(percentage_text)
        columns = ["name", "symbol", "currency", "quantity", "평가금액", "평가손익", "수익률", "비중"]
        st.dataframe(
            display[columns].rename(columns={
                "name": "종목", "symbol": "심볼", "currency": "통화", "quantity": "수량"
            }),
            use_container_width=True,
            hide_index=True,
        )
        st.caption("비중은 환율 왜곡을 피하기 위해 각 통화 안에서 계산합니다.")
    with tab_allocation:
        for currency_code, items in scoped.groupby("currency"):
            grouped = items.groupby(["symbol", "name"], dropna=False, as_index=False)["market_value"].sum()
            grouped["label"] = grouped["name"].fillna(grouped["symbol"])
            figure = px.pie(
                grouped,
                values="market_value",
                names="label",
                hole=0.58,
                title=f"{currency_code} 자산배분",
            )
            figure.update_layout(margin=dict(l=10, r=10, t=55, b=10), legend_title_text="종목")
            st.plotly_chart(figure, use_container_width=True, config={"displayModeBar": False})


def render_watchlist_placeholder() -> None:
    _page_header(
        "관심종목",
        "관심종목 기능은 다음 단계에서 목표가와 메모까지 연결됩니다.",
        live=False,
        timestamp="준비 중",
    )
    st.info("현재는 메뉴 구조만 먼저 마련했습니다. 기존 시장 화면에서 종목을 탐색할 수 있습니다.")
