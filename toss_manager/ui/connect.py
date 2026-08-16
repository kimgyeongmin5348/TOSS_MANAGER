"""Optional Toss real-time API connection."""

import streamlit as st
from sqlalchemy import Engine
from sqlalchemy.exc import SQLAlchemyError

from toss_manager.client import TossAPIClient, TossAPIError
from toss_manager.config import Settings
from toss_manager.network import get_public_ipv4, is_ip_not_allowed
from toss_manager.repository import sync_user_and_accounts


@st.cache_data(ttl=300, show_spinner=False)
def _current_server_ip() -> str | None:
    try:
        return get_public_ipv4()
    except Exception:
        return None


def render_server_ip_guide() -> None:
    ip = _current_server_ip()
    st.markdown("##### 토스 Open API 허용 IP")
    if ip:
        st.code(ip, language=None)
        st.caption(
            "배포된 Porto 서버의 현재 출발 IP입니다. 토스증권 WTS → 설정 → "
            "Open API의 허용 IP에 등록해 주세요. Streamlit 서버가 재배치되면 바뀔 수 있습니다."
        )
    else:
        st.warning("현재 서버의 공인 IPv4를 확인하지 못했습니다. 잠시 후 새로고침해 주세요.")


def render_realtime_connect(
    engine: Engine, user_id: int, email: str, *, sidebar: bool = False
) -> None:
    if sidebar:
        with st.sidebar:
            _render_realtime_connect_content(engine, user_id, email)
        return
    _render_realtime_connect_content(engine, user_id, email)


def _render_realtime_connect_content(engine: Engine, user_id: int, email: str) -> None:
    with st.expander("토스 실시간 연결", expanded=True):
        st.caption("키는 현재 세션에서만 사용되며 DB에 저장되지 않습니다.")
        render_server_ip_guide()
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
                if is_ip_not_allowed(exc):
                    st.error(
                        "현재 Porto 서버 IP가 토스 Open API 허용 목록에 없습니다. "
                        "위 IP를 등록한 뒤 다시 연결해 주세요."
                    )
                else:
                    st.error(f"실시간 연결에 실패했습니다: {exc}")
