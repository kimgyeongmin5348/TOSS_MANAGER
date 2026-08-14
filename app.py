"""Streamlit application entry point."""

from __future__ import annotations

import streamlit as st
import time
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from toss_manager.client import TossAPIError
from toss_manager.config import DatabaseSettings
from toss_manager.database import check_connection, initialize_schema, make_engine
from toss_manager.repository import save_portfolio_snapshot, sync_instruments
from toss_manager.ui.auth_view import render_auth_view
from toss_manager.ui.connect import render_realtime_connect
from toss_manager.ui.conditional_orders import render_conditional_orders
from toss_manager.ui.market import render_market_view
from toss_manager.ui.saved import render_saved_view
from toss_manager.ui.sidebar import load_holdings, render_sidebar
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

    if "client" not in st.session_state:
        name = st.session_state.get("display_name") or st.session_state.user_email
        st.markdown(f"### 안녕하세요, {name}님")
        if st.button("로그아웃"):
            st.session_state.clear()
            st.rerun()
        render_saved_view(engine, int(st.session_state.user_id))
        render_realtime_connect(
            engine, int(st.session_state.user_id), st.session_state.user_email
        )
        return

    client = st.session_state.client
    st.sidebar.markdown(
        '<div class="brand"><span class="mark">P</span>porto</div>',
        unsafe_allow_html=True,
    )
    st.sidebar.caption("● TiDB 연결됨")
    try:
        holdings, account_seq = load_holdings(client, st.session_state.accounts)
        sync_instruments(engine, holdings)
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
    page = st.sidebar.radio(
        "메뉴",
        ["시장·차트", "조건주문"],
        key="main_page",
        horizontal=True,
    )
    render_sidebar(holdings)
    if page == "조건주문":
        render_conditional_orders(client, account_seq)
    else:
        render_market_view(client, holdings, engine)


if __name__ == "__main__":
    main()
