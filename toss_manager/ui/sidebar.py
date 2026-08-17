"""Account selector and holdings sidebar."""

import pandas as pd
import streamlit as st

from toss_manager.client import TossAPIClient
from toss_manager.transform import holdings_frame

from .formatting import currency, percentage, percentage_text


NAVIGATION_ITEMS = (
    ("홈", "🏠"),
    ("포트폴리오", "💼"),
    ("시장", "📈"),
    ("관심종목", "⭐"),
    ("조건주문", "🔔"),
    ("계정 관리", "⚙️"),
)


def render_navigation() -> str:
    """Render card-style sidebar navigation and return the selected page."""
    pages = [page for page, _ in NAVIGATION_ITEMS]
    if st.session_state.get("main_page") not in pages:
        st.session_state.main_page = "홈"
    st.sidebar.markdown('<div class="side-title nav-title">MENU</div>', unsafe_allow_html=True)
    for page, icon in NAVIGATION_ITEMS:
        active = page == st.session_state.main_page
        key = f"nav_{'active' if active else 'idle'}_{page}"
        if st.sidebar.button(
            f"{icon}　{page}",
            key=key,
            use_container_width=True,
        ):
            st.session_state.main_page = page
            st.rerun()
    return str(st.session_state.main_page)


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


def load_portfolio_holdings(
    client: TossAPIClient, accounts: list[dict]
) -> tuple[pd.DataFrame, pd.DataFrame, int]:
    """Load every account once and return all holdings plus the selected account."""
    labels = {
        f"{account.get('accountNo', '계좌')} · {account.get('accountType', '')}": int(
            account["accountSeq"]
        )
        for account in accounts
    }
    selected = st.sidebar.selectbox("조회 계좌", labels, key="portfolio_account")
    selected_seq = labels[selected]
    account_by_seq = {int(account["accountSeq"]): account for account in accounts}
    frames: list[pd.DataFrame] = []
    for account_seq, account in account_by_seq.items():
        frame = holdings_frame(client.get_holdings(account_seq), account_seq)
        if frame.empty:
            continue
        account_no = str(account.get("accountNo") or "")
        visible = "".join(character for character in account_no if character.isalnum())[-4:]
        frame["account_no_masked"] = f"****{visible}" if visible else "계좌"
        frame["account_type"] = account.get("accountType") or "계좌"
        frames.append(frame)
    all_holdings = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if all_holdings.empty:
        return all_holdings, all_holdings, selected_seq
    selected_holdings = all_holdings[
        pd.to_numeric(all_holdings["account_seq"], errors="coerce").eq(selected_seq)
    ].copy()
    return all_holdings, selected_holdings, selected_seq


def render_sidebar(frame: pd.DataFrame) -> None:
    st.sidebar.markdown(
        '<div class="side-title">MY HOLDINGS</div>', unsafe_allow_html=True
    )
    if frame.empty:
        st.sidebar.caption("보유 종목이 없습니다.")

    for index, holding in enumerate(frame.itertuples()):
        rate = percentage(holding.profit_loss_rate)
        rate_tone = "up" if rate > 0 else "down" if rate < 0 else "flat"
        market = "US" if str(holding.currency) == "USD" else "KR"
        quantity = float(holding.quantity or 0)
        quantity_text = f"{quantity:,.4f}".rstrip("0").rstrip(".")
        if st.sidebar.button(
            f"**{holding.name or holding.symbol}**　"
            f"{percentage_text(holding.profit_loss_rate)}  \n"
            f"{holding.symbol} · {quantity_text}주 · 평단 "
            f"{currency(float(holding.average_purchase_price or 0), market)}",
            key=f"holding_{rate_tone}_{index}",
            use_container_width=True,
        ):
            st.session_state.selected_symbol = str(holding.symbol).upper()
            st.session_state.selected_market = market
            st.session_state.market_selector = "미장" if market == "US" else "국장"
            st.rerun()

    st.sidebar.write("")
    from toss_manager.session import render_logout_button
    render_logout_button(key="live_logout")
