"""Porto registration and login screen."""

import streamlit as st
from sqlalchemy import Engine
from sqlalchemy.exc import SQLAlchemyError

from toss_manager.client import TossAPIClient, TossAPIError
from toss_manager.config import Settings
from toss_manager.network import is_ip_not_allowed
from toss_manager.repository import (
    authenticate_user,
    register_user,
    sync_user_and_accounts,
)
from toss_manager.ui.connect import render_server_ip_guide
from toss_manager.ui.disclaimer import render_investment_disclaimer


def render_auth_view(engine: Engine) -> None:
    st.markdown('''<div class="auth-brand">
        <div class="auth-brand-left"><span class="mark">P</span><b>porto</b></div>
        <span>PORTFOLIO INTELLIGENCE</span>
    </div>''', unsafe_allow_html=True)
    introduction, login = st.columns([1.12, 0.88], gap="large", vertical_alignment="center")
    with introduction:
        st.markdown('''<section class="auth-hero">
          <div class="auth-kicker"><span></span> TOSS SECURITIES PORTFOLIO</div>
          <h1>투자 기록은 차곡차곡,<br><em>판단은 더 선명하게.</em></h1>
          <p class="auth-lead">Porto는 토스증권의 보유 자산과 시장 데이터를 한곳에 모아<br>
          내 투자 현황을 기록하고 탐색할 수 있는 개인 포트폴리오 대시보드입니다.</p>
          <div class="auth-features">
            <div><span>01</span><b>포트폴리오 기록</b><p>보유 종목과 수익률을<br>스냅샷으로 저장해요.</p></div>
            <div><span>02</span><b>실시간 시장 탐색</b><p>국내·미국 종목과<br>캔들 흐름을 확인해요.</p></div>
            <div><span>03</span><b>안전한 연결</b><p>API 키는 저장하지 않고<br>현재 세션에서만 사용해요.</p></div>
          </div>
          <div class="auth-mode-note"><b>두 가지 방식으로 이용하세요</b>
            <span>Porto 로그인으로 저장된 기록을 보고, 필요할 때만 토스 Open API를 연결해 실시간 데이터를 확인할 수 있어요.</span>
          </div>
        </section>''', unsafe_allow_html=True)
    with login:
        with st.container(border=True):
            st.markdown('''<div class="auth-card-head">
              <span class="auth-lock">P</span>
              <div><h3>Porto에 로그인</h3><p>저장된 나의 투자 기록을 확인하세요.</p></div>
            </div>''', unsafe_allow_html=True)
            with st.form("porto_login"):
                email = st.text_input(
                    "아이디 (이메일)", key="login_email", placeholder="name@example.com"
                )
                password = st.text_input(
                    "비밀번호", type="password", key="login_password",
                    placeholder="비밀번호를 입력하세요",
                )
                submitted = st.form_submit_button(
                    "저장된 포트폴리오 보기  →", use_container_width=True
                )
            if submitted:
                _login(engine, email, password)
            st.markdown('<div class="auth-divider"><span>처음 방문하셨나요?</span></div>', unsafe_allow_html=True)
            if st.button("새 계정 만들기", use_container_width=True, type="secondary"):
                signup_dialog(engine)
            st.markdown('''<div class="auth-safe"><span>✓</span><p><b>안전하게 관리해요</b><br>
            비밀번호는 해시로 저장되며 토스 API 키는 데이터베이스에 저장하지 않습니다.</p></div>''', unsafe_allow_html=True)
            render_investment_disclaimer(compact=True)


@st.dialog("Porto 회원가입")
def signup_dialog(engine: Engine) -> None:
    st.caption("토스 계좌 확인 후 가입됩니다. API 키는 DB에 저장하지 않습니다.")
    render_server_ip_guide()
    with st.form("porto_signup"):
        name = st.text_input("표시 이름")
        email = st.text_input("아이디 (이메일)", key="signup_email")
        password = st.text_input(
            "비밀번호 (8자 이상)", type="password", key="signup_password"
        )
        confirmation = st.text_input("비밀번호 확인", type="password")
        st.markdown("##### 토스증권 Open API 연결")
        client_id = st.text_input("Client ID", key="signup_client_id")
        client_secret = st.text_input(
            "Client Secret", type="password", key="signup_client_secret"
        )
        submitted = st.form_submit_button("회원가입 완료", use_container_width=True)
    if not submitted:
        return
    if password != confirmation:
        st.error("비밀번호 확인이 일치하지 않습니다.")
        return
    if not client_id.strip() or not client_secret.strip():
        st.error("Client ID와 Client Secret을 모두 입력해 주세요.")
        return
    try:
        client = TossAPIClient(Settings(client_id.strip(), client_secret.strip()))
        accounts = client.get_accounts()
        if not accounts:
            st.error("조회 가능한 토스증권 계좌가 없습니다.")
            return
        user_id = register_user(engine, email, name, password)
        sync_user_and_accounts(
            engine,
            email=email,
            display_name=name,
            accounts=accounts,
        )
        _set_session(user_id, email.strip().lower(), name.strip() or None)
        st.session_state.client = client
        st.session_state.accounts = accounts
        st.rerun()
    except TossAPIError as exc:
        if is_ip_not_allowed(exc):
            st.error("위 Porto 서버 IP를 토스 Open API 허용 목록에 등록한 뒤 다시 시도해 주세요.")
        else:
            st.error(f"토스 Open API 연결에 실패했습니다: {exc}")
    except ValueError as exc:
        st.error(str(exc))
    except SQLAlchemyError:
        st.error("회원가입 정보를 저장하지 못했습니다.")


def _login(engine: Engine, email: str, password: str) -> None:
    try:
        user = authenticate_user(engine, email, password)
    except SQLAlchemyError:
        st.error("로그인 정보를 확인하지 못했습니다.")
        return
    if not user:
        st.error("이메일 또는 비밀번호가 올바르지 않습니다.")
        return
    _set_session(int(user["user_id"]), user["email"], user["display_name"])
    st.rerun()


def _set_session(user_id: int, email: str, display_name: str | None) -> None:
    st.session_state.user_id = user_id
    st.session_state.user_email = email
    st.session_state.display_name = display_name
