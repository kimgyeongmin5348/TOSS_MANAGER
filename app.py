"""Streamlit application entry point."""

from __future__ import annotations

import streamlit as st
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from toss_manager.client import TossAPIError
from toss_manager.config import DatabaseSettings
from toss_manager.database import check_connection, initialize_schema, make_engine
from toss_manager.ui.connect import render_connect_view
from toss_manager.ui.market import render_market_view
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
        connect_database()
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

    if "client" not in st.session_state:
        render_connect_view()
        return

    client = st.session_state.client
    st.sidebar.markdown(
        '<div class="brand"><span class="mark">P</span>porto</div>',
        unsafe_allow_html=True,
    )
    st.sidebar.caption("● TiDB 연결됨")
    try:
        holdings, _ = load_holdings(client, st.session_state.accounts)
    except TossAPIError as exc:
        st.error(f"계좌를 불러오지 못했습니다: {exc}")
        return
    render_sidebar(holdings)
    render_market_view(client, holdings)


if __name__ == "__main__":
    main()
