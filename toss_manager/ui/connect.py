"""Toss API credential connection screen."""

import streamlit as st

from toss_manager.client import TossAPIClient, TossAPIError
from toss_manager.config import Settings


def render_connect_view() -> None:
    st.markdown('<div class="brand"><span class="mark">P</span>porto <span style="margin-left:auto;font-size:.7rem;color:#9299a7;font-weight:500">PORTFOLIO INTELLIGENCE</span></div>', unsafe_allow_html=True)
    introduction, connection = st.columns(
        [1.18, 0.82], gap="large", vertical_alignment="center"
    )
    with introduction:
        st.markdown('''<div class="login-shell">
        <div><span class="login-kicker">● TOSS SECURITIES OPEN API</span></div>
        <h1 class="login-title">내 투자를 더 선명하게,<br>한 화면에서.</h1>
        <p class="login-copy">토스증권 계좌를 연결하면 보유 종목부터 국내·미국 시장 순위와<br>캔들 차트까지 한곳에서 확인할 수 있어요.</p>
        <div class="brand-story"><b>porto</b><i></i><span>Portfolio, organized. 흩어진 투자 정보를 한곳에.</span></div>
        <div class="feature-grid">
          <div class="feature"><span class="feature-icon">01</span><strong>보유 자산 분석</strong><small>평단가와 수익률을<br>자동으로 정리해요.</small></div>
          <div class="feature"><span class="feature-icon">02</span><strong>시장 탐색</strong><small>국내·미국 거래량 순위를<br>실시간으로 확인해요.</small></div>
          <div class="feature"><span class="feature-icon">03</span><strong>차트 분석</strong><small>다양한 주기의 캔들로<br>흐름을 살펴봐요.</small></div>
        </div></div>''', unsafe_allow_html=True)

    with connection:
        st.markdown('<div class="login-card"><div class="login-card-head"><span class="login-logo">T</span><div><h3>토스증권 계좌 연결</h3><p>Open API 키로 안전하게 시작하세요.</p></div></div>', unsafe_allow_html=True)
        with st.form("connect", border=False):
            client_id = st.text_input("Client ID", placeholder="발급받은 Client ID")
            client_secret = st.text_input(
                "Client Secret", type="password", placeholder="발급받은 Client Secret"
            )
            submitted = st.form_submit_button(
                "안전하게 계좌 연결하기  →", use_container_width=True
            )
        st.markdown('''<div class="secure-note"><span>🔒</span><span><b>읽기 전용으로 연결돼요.</b><br>입력한 키는 데이터베이스에 저장하지 않으며 주문 권한을 사용하지 않습니다.</span></div>
        <div class="steps"><b>1. API 키 입력</b><span>—</span><span>2. 계좌 확인</span><span>—</span><span>3. 분석 시작</span></div>
        <div class="login-help">API 키가 없나요? 토스증권 WTS의 <a href="https://developers.tossinvest.com/docs" target="_blank">Open API 설정 안내</a>를 확인하세요.</div></div>''', unsafe_allow_html=True)
        if submitted:
            _connect(client_id, client_secret)


def _connect(client_id: str, client_secret: str) -> None:
    if not client_id.strip() or not client_secret.strip():
        st.error("두 항목을 모두 입력해 주세요.")
        return
    try:
        client = TossAPIClient(Settings(client_id.strip(), client_secret.strip()))
        accounts = client.get_accounts()
        if not accounts:
            st.warning("조회 가능한 계좌가 없습니다.")
            return
        st.session_state.client = client
        st.session_state.accounts = accounts
        st.rerun()
    except (TossAPIError, ValueError, KeyError) as exc:
        st.error(f"연결에 실패했습니다: {exc}")
