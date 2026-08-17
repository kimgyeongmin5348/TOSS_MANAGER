"""Streamlit application entry point."""

from __future__ import annotations

import streamlit as st
import time
import logging
from datetime import datetime, timezone
import pandas as pd
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from toss_manager.client import TossAPIError
from toss_manager.accounts import current_session_version
from toss_manager.config import DatabaseSettings
from toss_manager.database import check_connection, initialize_schema, make_engine
from toss_manager.repository import (
    load_portfolio_history,
    load_saved_portfolio,
    sync_instruments,
)
from toss_manager.snapshots import (
    cleanup_old_intraday_snapshots,
    closing_snapshot_types,
    latest_snapshot_status,
    save_snapshot,
)
from toss_manager.session import logout, render_logout_button, session_is_valid
from toss_manager.ui.auth_view import render_auth_view
from toss_manager.ui.account import render_account_view
from toss_manager.ui.connect import render_realtime_connect
from toss_manager.ui.conditional_orders import render_conditional_orders
from toss_manager.ui.market import render_market_view
from toss_manager.ui.portfolio import (
    render_home,
    render_portfolio,
)
from toss_manager.ui.snapshot_status import render_snapshot_status
from toss_manager.ui.watchlist import render_watchlist
from toss_manager.ui.saved import render_risk_overview, render_saved_view
from toss_manager.ui.sidebar import (
    load_portfolio_holdings,
    render_navigation,
    render_sidebar,
)
from toss_manager.ui.styles import CSS


LOGGER = logging.getLogger(__name__)


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
    except ValueError as exc:
        st.error("TiDB 연결 또는 스키마 초기화에 실패했습니다.")
        st.caption(str(exc))
        st.stop()
    except RuntimeError:
        LOGGER.exception("Database schema initialization failure")
        st.error("TiDB 스키마 초기화에 실패했습니다. 관리자 로그를 확인해 주세요.")
        st.stop()

    if "user_id" not in st.session_state:
        render_auth_view(engine)
        return
    if not session_is_valid():
        logout(notice="로그인 세션이 만료되었습니다. 다시 로그인해 주세요.")
    try:
        active_version = current_session_version(
            engine, user_id=int(st.session_state.user_id)
        )
        if active_version != int(st.session_state.get("session_version", 1)):
            logout(notice="계정 보안 정보가 변경되어 다시 로그인해야 합니다.")
    except SQLAlchemyError:
        # A DB outage must not hide an already-running Toss live view.
        LOGGER.exception("Session version check failed; retaining bounded local session")

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
        try:
            latest_db = latest_snapshot_status(engine, user_id)
        except SQLAlchemyError:
            LOGGER.exception("Snapshot status read failed")
            latest_db = None
        render_snapshot_status(
            live_queried_at=None, latest_db=latest_db,
            save_state=st.session_state.get("snapshot_save_state"), live=False,
        )
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
            render_watchlist(engine, user_id=user_id)
        elif page == "계정 관리":
            render_account_view(engine, user_id)
        else:
            st.info("조건주문을 확인하려면 토스 Open API를 실시간 연결해 주세요.")
        render_realtime_connect(
            engine, user_id, st.session_state.user_email, sidebar=True
        )
        render_logout_button(key="offline_logout")
        return

    client = st.session_state.client
    try:
        all_holdings, holdings, account_seq = load_portfolio_holdings(
            client, st.session_state.accounts
        )
    except TossAPIError as exc:
        st.error(f"계좌를 불러오지 못했습니다: {exc}")
        return
    live_queried_at = datetime.now(timezone.utc)
    st.session_state.last_live_query_at = live_queried_at
    try:
        sync_instruments(engine, all_holdings)
    except SQLAlchemyError:
        LOGGER.exception("Instrument save failed; live holdings remain available")
        st.session_state.snapshot_save_state = {
            "status": "failed", "message": "종목 DB 저장 실패"
        }

    manual_save = st.sidebar.button(
        "현재 상태 저장", type="primary", key="save_current_snapshot"
    )
    retry_save = (
        st.session_state.get("snapshot_save_state", {}).get("status") == "failed"
        and st.sidebar.button("DB 저장 재시도", key="retry_snapshot_save")
    )
    connect_pending = bool(st.session_state.pop("snapshot_connect_pending", False))
    now_value = time.time()
    auto_due = now_value - float(st.session_state.get("last_snapshot_attempt", 0)) >= 60
    if connect_pending or manual_save or retry_save or auto_due:
        reason = "CONNECT" if connect_pending else "MANUAL" if manual_save or retry_save else "AUTO"
        st.session_state.last_snapshot_attempt = now_value
        try:
            results = []
            account_sequences = [
                int(item["accountSeq"]) for item in st.session_state.accounts
            ]
            for seq in account_sequences:
                account_holdings = (
                    all_holdings[
                        pd.to_numeric(
                            all_holdings["account_seq"], errors="coerce"
                        ).eq(seq)
                    ].copy()
                    if not all_holdings.empty else pd.DataFrame()
                )
                result = save_snapshot(
                    engine, user_id=user_id, account_seq=seq,
                    holdings=account_holdings, reason=reason,
                )
                results.append(result)
                for close_type in closing_snapshot_types(account_holdings):
                    results.append(save_snapshot(
                        engine, user_id=user_id, account_seq=seq,
                        holdings=account_holdings, reason="CLOSE",
                        snapshot_type=close_type,
                    ))
            if results:
                saved = [item for item in results if item.status == "saved"]
                result = saved[-1] if saved else results[-1]
                st.session_state.snapshot_save_state = {
                    "status": result.status, "message": result.message,
                    "captured_at": result.captured_at, "saved_at": result.saved_at,
                }
            cleanup_key = datetime.now(timezone.utc).date().isoformat()
            if st.session_state.get("snapshot_cleanup_date") != cleanup_key:
                cleanup_old_intraday_snapshots(engine)
                st.session_state.snapshot_cleanup_date = cleanup_key
        except SQLAlchemyError:
            LOGGER.exception("Portfolio snapshot save failed; live view continues")
            st.session_state.snapshot_save_state = {
                "status": "failed", "message": "DB 저장 실패"
            }

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
        render_watchlist(engine, user_id=user_id, client=client)
    elif page == "계정 관리":
        render_account_view(engine, user_id)
    else:
        render_conditional_orders(client, account_seq)


if __name__ == "__main__":
    main()
