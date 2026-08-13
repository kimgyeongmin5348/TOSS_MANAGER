"""Account selector and holdings sidebar."""

import pandas as pd
import streamlit as st

from toss_manager.client import TossAPIClient
from toss_manager.transform import holdings_frame

from .common import currency


def load_holdings(
    client: TossAPIClient, accounts: list[dict]
) -> tuple[pd.DataFrame, int]:
    labels = {
        f"{account.get('accountNo', '계좌')} · {account.get('accountType', '')}": int(
            account["accountSeq"]
        )
        for account in accounts
    }
    selected = st.sidebar.selectbox("계좌", labels)
    account_seq = labels[selected]
    return holdings_frame(client.get_holdings(account_seq), account_seq), account_seq


def render_sidebar(frame: pd.DataFrame) -> None:
    st.sidebar.markdown(
        '<div class="side-title">MY HOLDINGS</div>', unsafe_allow_html=True
    )
    if frame.empty:
        st.sidebar.caption("보유 종목이 없습니다.")

    for holding in frame.itertuples():
        rate = float(holding.profit_loss_rate or 0)
        market = "US" if str(holding.currency) == "USD" else "KR"
        quantity = float(holding.quantity or 0)
        quantity_text = f"{quantity:,.4f}".rstrip("0").rstrip(".")
        if st.sidebar.button(
            f"**{holding.name or holding.symbol}**　{rate:+.2f}%  \n"
            f"{holding.symbol} · {quantity_text}주 · 평단 "
            f"{currency(float(holding.average_purchase_price or 0), market)}",
            key=f"holding_{market}_{holding.symbol}",
            use_container_width=True,
        ):
            st.session_state.selected_symbol = str(holding.symbol).upper()
            st.session_state.selected_market = market
            st.session_state.market_selector = "미장" if market == "US" else "국장"
            st.rerun()

    st.sidebar.write("")
    if st.sidebar.button("연결 해제"):
        st.session_state.clear()
        st.rerun()
