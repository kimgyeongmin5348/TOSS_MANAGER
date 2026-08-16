"""Streamlit application entry point."""

from __future__ import annotations

import streamlit as st
import time
import pandas as pd
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from toss_manager.client import TossAPIError
from toss_manager.config import DatabaseSettings
from toss_manager.database import check_connection, initialize_schema, make_engine
from toss_manager.repository import (
    load_portfolio_history,
    load_saved_portfolio,
    save_portfolio_snapshot,
    sync_instruments,
)
from toss_manager.ui.auth_view import render_auth_view
from toss_manager.ui.connect import render_realtime_connect
from toss_manager.ui.conditional_orders import render_conditional_orders
from toss_manager.ui.market import render_market_view
from toss_manager.ui.portfolio import (
    render_home,
    render_portfolio,
    render_watchlist_placeholder,
)
from toss_manager.ui.saved import render_risk_overview, render_saved_view
from toss_manager.ui.sidebar import (
    load_portfolio_holdings,
    render_navigation,
    render_sidebar,
)
from toss_manager.ui.styles import CSS


st.set_page_config(
    page_title="Porto | 투자 포트폴리오",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_resource(show_spinner=False)
def connect_database() -> Engine:
    engine = make_engine(DatabaseSettings.from_env())
    check_connection(engine)
    initialize_schema(engine)
    return engine


def main() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    try:
        engine = connect_database()
    except SQLAlchemyError:
        st.error(
            "TiDB에 연결하지 못했습니다. `.env`의 호스트, 사용자명, "
            "비밀번호와 접근 허용 범위를 확인해 주세요."
        )
        st.stop()
    except (ValueError, RuntimeError) as exc:
        st.error("TiDB 연결 또는 스키마 초기화에 실패했습니다.")
        st.caption(str(exc))
        st.stop()

    if "user_id" not in st.session_state:
        render_auth_view(engine)
        return

    st.sidebar.markdown(
        '<div class="brand"><span class="mark">P</span>porto</div>',
        unsafe_allow_html=True,
    )
    live = "client" in st.session_state
    st.sidebar.caption("● 실시간 연결됨" if live else "● 저장 데이터 모드")
    page = render_navigation()
    user_id = int(st.session_state.user_id)
    try:
        history = load_portfolio_history(engine, user_id)
    except SQLAlchemyError:
        history = []

    if not live:
        try:
            holdings = pd.DataFrame(load_saved_portfolio(engine, user_id))
        except SQLAlchemyError:
            st.error("저장된 포트폴리오를 불러오지 못했습니다.")
            holdings = pd.DataFrame()
        if page == "홈":
            render_home(
                holdings,
                display_name=st.session_state.get("display_name"),
                live=False,
                history=history,
            )
            if not holdings.empty:
                render_risk_overview(engine, user_id, holdings)
        elif page == "포트폴리오":
            render_portfolio(holdings, live=False)
        elif page == "시장":
            render_saved_view(engine, user_id)
        elif page == "관심종목":
            render_watchlist_placeholder()
        else:
            st.info("조건주문을 확인하려면 토스 Open API를 실시간 연결해 주세요.")
        render_realtime_connect(
            engine, user_id, st.session_state.user_email, sidebar=True
        )
        if st.sidebar.button("로그아웃", key="offline_logout"):
            st.session_state.clear()
            st.rerun()
        return

    client = st.session_state.client
    try:
        all_holdings, holdings, account_seq = load_portfolio_holdings(
            client, st.session_state.accounts
        )
        sync_instruments(engine, all_holdings)
        snapshot_key = f"last_snapshot_{account_seq}"
        now = time.time()
        if now - st.session_state.get(snapshot_key, 0) >= 60:
            save_portfolio_snapshot(
                engine,
                user_id=int(st.session_state.user_id),
                account_seq=account_seq,
                holdings=holdings,
            )
            st.session_state[snapshot_key] = now
    except TossAPIError as exc:
        st.error(f"계좌를 불러오지 못했습니다: {exc}")
        return
    except SQLAlchemyError:
        st.error("보유 종목을 TiDB에 저장하지 못했습니다.")
        return
    render_sidebar(holdings)
    if page == "홈":
        render_home(
            all_holdings,
            display_name=st.session_state.get("display_name"),
            live=True,
            history=history,
        )
        if not all_holdings.empty:
            render_risk_overview(engine, user_id, all_holdings)
    elif page == "포트폴리오":
        render_portfolio(all_holdings, live=True)
    elif page == "시장":
        render_market_view(client, holdings, engine)
    elif page == "관심종목":
        render_watchlist_placeholder()
    else:
        render_conditional_orders(client, account_seq)


if __name__ == "__main__":
    main()
