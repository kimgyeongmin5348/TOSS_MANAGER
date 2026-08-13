"""Optional Toss real-time API connection."""

import streamlit as st
from sqlalchemy import Engine
from sqlalchemy.exc import SQLAlchemyError

from toss_manager.client import TossAPIClient, TossAPIError
from toss_manager.config import Settings
from toss_manager.repository import sync_user_and_accounts


def render_realtime_connect(engine: Engine, user_id: int, email: str) -> None:
    with st.expander("토스 실시간 연결", expanded=True):
        st.caption("키는 현재 세션에서만 사용되며 DB에 저장되지 않습니다.")
        with st.form("toss_connect"):
            client_id = st.text_input("Client ID")
            client_secret = st.text_input("Client Secret", type="password")
            submitted = st.form_submit_button("실시간 조회 시작", use_container_width=True)
        if submitted:
            if not client_id.strip() or not client_secret.strip():
                st.error("Client ID와 Client Secret을 모두 입력해 주세요.")
                return
            try:
                client = TossAPIClient(Settings(client_id.strip(), client_secret.strip()))
                accounts = client.get_accounts()
                if not accounts:
                    st.warning("조회 가능한 계좌가 없습니다.")
                    return
                synced_user_id = sync_user_and_accounts(
                    engine, email=email,
                    display_name=st.session_state.get("display_name"), accounts=accounts,
                )
                if synced_user_id != user_id:
                    raise RuntimeError("로그인 사용자와 계좌 사용자가 일치하지 않습니다.")
                st.session_state.client = client
                st.session_state.accounts = accounts
                st.rerun()
            except SQLAlchemyError:
                st.error("계좌 정보를 저장하지 못했습니다.")
            except (TossAPIError, ValueError, KeyError, RuntimeError) as exc:
                st.error(f"실시간 연결에 실패했습니다: {exc}")
