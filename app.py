"""Streamlit portfolio dashboard using the same package as the notebook."""

import plotly.express as px
import streamlit as st

from toss_manager.client import TossAPIClient, TossAPIError
from toss_manager.config import Settings
from toss_manager.transform import candles_frame, holdings_frame


@st.cache_resource
def get_client() -> TossAPIClient:
    return TossAPIClient(Settings.from_env())


def main() -> None:
    st.set_page_config(page_title="개인 투자 분석", layout="wide")
    st.title("개인 투자자 포트폴리오 및 투자 분석")
    st.caption("조회 전용 초기 버전 · 토스증권 Open API 1.2.14")
    try:
        client = get_client()
        accounts = client.get_accounts()
    except (ValueError, TossAPIError) as exc:
        st.error(str(exc))
        st.info(".env 설정과 토스증권의 허용 IP 등록 여부를 확인하세요.")
        return
    if not accounts:
        st.warning("조회 가능한 종합매매 계좌가 없습니다.")
        return

    labels = {f"{a['accountNo']} ({a['accountType']})": int(a['accountSeq']) for a in accounts}
    selected = st.sidebar.selectbox("계좌", labels)
    account_seq = labels[selected]
    holdings = holdings_frame(client.get_holdings(account_seq), account_seq)
    if holdings.empty:
        st.info("보유 종목이 없습니다.")
        return

    c1, c2, c3 = st.columns(3)
    c1.metric("평가금액 (통화 혼합 전)", f"{holdings['market_value'].sum():,.2f}")
    c2.metric("평가손익 (통화 혼합 전)", f"{holdings['profit_loss'].sum():,.2f}")
    c3.metric("보유 종목", f"{len(holdings):,}")
    st.warning("KRW와 USD는 환율 변환 전 합산하면 의미가 없습니다. 아래 차트는 통화별로 분리합니다.")
    st.plotly_chart(px.sunburst(holdings, path=["currency", "name"], values="market_value"), use_container_width=True)
    st.dataframe(holdings.drop(columns=["account_seq"]), use_container_width=True, hide_index=True)

    symbol = st.selectbox("차트 종목", holdings["symbol"].tolist())
    candle_payload = client.get_candles(symbol, interval="1d", count=100)
    candles = candles_frame(candle_payload, symbol, "1d")
    if not candles.empty:
        st.line_chart(candles.set_index("timestamp")["close_price"])


if __name__ == "__main__":
    main()
