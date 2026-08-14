"""Shared investment-information disclaimer."""

import streamlit as st


DISCLAIMER = (
    "Porto가 제공하는 차트, 점수, 예측, 뉴스 및 분석은 투자 참고를 위한 정보이며 "
    "특정 금융상품의 매수·매도를 권유하거나 수익을 보장하지 않습니다. 정보에는 지연·오류가 "
    "있을 수 있으며, 최종 투자 판단과 그에 따른 손익은 이용자 본인에게 있습니다."
)


def render_investment_disclaimer(*, compact: bool = False) -> None:
    if compact:
        st.caption(f"※ {DISCLAIMER}")
    else:
        st.warning(DISCLAIMER, icon="⚠️")
