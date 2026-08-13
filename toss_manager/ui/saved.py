"""Database-only portfolio view."""

import pandas as pd
import streamlit as st
from sqlalchemy import Engine
from sqlalchemy.exc import SQLAlchemyError

from toss_manager.repository import load_saved_portfolio

from .common import currency


def render_saved_view(engine: Engine, user_id: int) -> None:
    st.subheader("저장된 포트폴리오")
    st.caption("마지막 실시간 연결에서 저장한 데이터입니다.")
    try:
        rows = load_saved_portfolio(engine, user_id)
    except SQLAlchemyError:
        st.error("저장된 포트폴리오를 불러오지 못했습니다.")
        return
    if not rows:
        st.info("저장된 보유 종목이 없습니다. 토스 실시간 연결을 먼저 진행해 주세요.")
        return
    frame = pd.DataFrame(rows)
    for account, items in frame.groupby(["account_no_masked", "account_type"], dropna=False):
        st.markdown(f"#### {account[0]} · {account[1] or '계좌'}")
        st.caption(f"저장 시각(UTC): {items.iloc[0]['captured_at']}")
        display = items.copy()
        display["현재가"] = display.apply(
            lambda row: currency(float(row["last_price"] or 0), "US" if row["currency"] == "USD" else "KR"), axis=1
        )
        display["평균 단가"] = display.apply(
            lambda row: currency(float(row["average_purchase_price"] or 0), "US" if row["currency"] == "USD" else "KR"), axis=1
        )
        st.dataframe(
            display[["name", "symbol", "quantity", "현재가", "평균 단가", "profit_loss_rate"]].rename(
                columns={"name": "종목", "symbol": "심볼", "quantity": "수량", "profit_loss_rate": "수익률"}
            ),
            use_container_width=True,
            hide_index=True,
        )
