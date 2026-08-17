"""Watchlist list, target status, notes, and editing UI."""

from __future__ import annotations

import logging

import streamlit as st
from sqlalchemy import Engine
from sqlalchemy.exc import SQLAlchemyError

from toss_manager.client import TossAPIClient, TossAPIError
from toss_manager.watchlist import (
    delete_watchlist_item,
    get_watchlist_item,
    load_watchlist,
    update_watchlist_prices,
    upsert_watchlist_item,
)

from .formatting import currency


LOGGER = logging.getLogger(__name__)


def render_watchlist_toggle(
    engine: Engine,
    *,
    user_id: int,
    symbol: str,
    market: str,
    name: str,
    last_price: float,
) -> None:
    try:
        item = get_watchlist_item(
            engine, user_id=user_id, symbol=symbol, market_country=market
        )
    except SQLAlchemyError:
        LOGGER.exception("Watchlist state read failure")
        st.warning("관심종목 상태를 불러오지 못했습니다.")
        return
    if item:
        if st.button("★ 관심종목 해제", key=f"watch_remove_{market}_{symbol}"):
            try:
                delete_watchlist_item(
                    engine, user_id=user_id, symbol=symbol, market_country=market
                )
                st.success("관심종목에서 해제했습니다.")
                st.rerun()
            except SQLAlchemyError:
                LOGGER.exception("Watchlist delete failure")
                st.error("관심종목을 해제하지 못했습니다.")
    elif st.button("☆ 관심종목 추가", key=f"watch_add_{market}_{symbol}"):
        try:
            upsert_watchlist_item(
                engine, user_id=user_id, symbol=symbol, market_country=market,
                name=name, currency="USD" if market == "US" else "KRW",
                last_price=last_price,
            )
            st.success("관심종목에 추가했습니다.")
            st.rerun()
        except SQLAlchemyError:
            LOGGER.exception("Watchlist insert failure")
            st.error("관심종목에 추가하지 못했습니다.")


def render_watchlist(
    engine: Engine, *, user_id: int, client: TossAPIClient | None = None
) -> None:
    st.title("관심종목")
    st.caption("메모와 목표가격은 사용자별로 저장되며 다른 계정과 공유되지 않습니다.")
    try:
        rows = load_watchlist(engine, user_id=user_id)
    except SQLAlchemyError:
        LOGGER.exception("Watchlist load failure")
        st.error("관심종목을 불러오지 못했습니다.")
        return
    if not rows:
        st.info("관심종목이 없습니다. 종목 상세 화면에서 ☆ 버튼을 눌러 추가해 주세요.")
        return

    if client:
        try:
            live_prices = client.get_prices([str(row["symbol"]) for row in rows])
            by_symbol = {str(item.get("symbol")).upper(): item for item in live_prices}
            for row in rows:
                item = by_symbol.get(str(row["symbol"]).upper())
                if item and item.get("lastPrice"):
                    row["last_price"] = item["lastPrice"]
            try:
                update_watchlist_prices(engine, user_id=user_id, prices=live_prices)
            except SQLAlchemyError:
                LOGGER.exception("Watchlist price save failure")
                st.warning("현재가는 표시하지만 가격 갱신 시각을 DB에 저장하지 못했습니다.")
        except TossAPIError:
            st.warning("실시간 관심종목 가격을 불러오지 못해 마지막 저장 가격을 표시합니다.")

    market_filter = st.segmented_control("시장", ["전체", "한국", "미국"], default="전체")
    market_code = {"한국": "KR", "미국": "US"}.get(market_filter or "전체")
    scoped = [row for row in rows if not market_code or row["market_country"] == market_code]
    if not scoped:
        st.info("선택한 시장의 관심종목이 없습니다.")
        return
    for row in scoped:
        _render_watchlist_row(engine, user_id, row)


def _render_watchlist_row(engine: Engine, user_id: int, row: dict) -> None:
    market = str(row["market_country"])
    symbol = str(row["symbol"])
    name = str(row.get("name") or symbol)
    current = float(row.get("last_price") or 0)
    target = float(row.get("target_price") or 0)
    reached = bool(current and target and current >= target)
    label = f"{name} · {symbol}"
    with st.expander(label, expanded=reached):
        columns = st.columns(3)
        columns[0].metric("현재가", currency(current, market) if current else "가격 없음")
        columns[1].metric("목표가격", currency(target, market) if target else "미설정")
        if current and target:
            gap = target - current
            gap_rate = gap / current * 100
            columns[2].metric("목표가까지", currency(gap, market), f"{gap_rate:+.2f}%")
            if reached:
                st.success("목표가격에 도달했습니다.")
            else:
                st.info("목표가격 도달 전입니다.")
        else:
            columns[2].metric("목표가까지", "-")

        news_count = int(row.get("news_count") or 0)
        sentiment = row.get("news_sentiment")
        if news_count:
            score = float(sentiment or 0)
            tone = "긍정" if score > 0.15 else "부정" if score < -0.15 else "중립"
            st.caption(f"최근 60일 뉴스 {news_count}건 · {tone} 요약")
            if row.get("latest_news_title"):
                st.write(f"최근 뉴스: {row['latest_news_title']}")
        else:
            st.caption("수집된 관심종목 뉴스가 없습니다. 실시간 종목 분석을 열면 뉴스가 갱신됩니다.")

        with st.form(f"watch_edit_{market}_{symbol}"):
            memo = st.text_area("사용자 메모", value=str(row.get("memo") or ""), max_chars=1000)
            target_input = st.number_input(
                "목표가격 (0은 미설정)", min_value=0.0, value=max(0.0, target),
                step=0.01 if market == "US" else 100.0,
            )
            save = st.form_submit_button("수정 저장", use_container_width=True)
        if save:
            try:
                upsert_watchlist_item(
                    engine, user_id=user_id, symbol=symbol, market_country=market,
                    name=name, currency=str(row.get("currency") or ("USD" if market == "US" else "KRW")),
                    memo=memo, target_price=target_input, last_price=current,
                )
                st.success("관심종목을 수정했습니다.")
                st.rerun()
            except SQLAlchemyError:
                LOGGER.exception("Watchlist update failure")
                st.error("관심종목을 수정하지 못했습니다.")
        if st.button("관심종목 삭제", key=f"watch_delete_{market}_{symbol}"):
            try:
                delete_watchlist_item(
                    engine, user_id=user_id, symbol=symbol, market_country=market
                )
                st.success("관심종목을 삭제했습니다.")
                st.rerun()
            except SQLAlchemyError:
                LOGGER.exception("Watchlist delete failure")
                st.error("관심종목을 삭제하지 못했습니다.")
