"""Company valuation and official financial-statement dialog."""

from html import escape

import streamlit as st
from sqlalchemy import Engine
from sqlalchemy.exc import SQLAlchemyError

from toss_manager.fundamentals.models import FundamentalResult
from toss_manager.fundamentals.providers import FundamentalsError
from toss_manager.fundamentals.service import load_company_fundamentals
from toss_manager.fundamentals.repository import save_fundamental_result


def _multiple(value: float | None) -> str:
    return "NM/자료 없음" if value is None else f"{value:,.1f}배"


def _money(value: float | None, currency: str) -> str:
    if value is None:
        return "자료 없음"
    unit = "조" if currency == "KRW" else "B"
    divisor = 1_000_000_000_000 if currency == "KRW" else 1_000_000_000
    prefix = "₩" if currency == "KRW" else "$"
    return f"{prefix}{value / divisor:,.2f}{unit}"


def _ratio_width(value: float | None, base: float | None) -> float:
    if value is None or base is None or base <= 0:
        return 0
    return max(3, min(100, abs(value / base) * 100))


def render_fundamentals_launcher(
    engine: Engine, *, symbol: str, name: str, market_country: str,
    market_price: float, shares_outstanding: float | None,
) -> None:
    if st.button("🏢 기업가치·재무제표", use_container_width=True, key=f"fundamentals_{market_country}_{symbol}"):
        with st.spinner("공식 공시 재무제표를 불러오고 있습니다..."):
            try:
                result = load_company_fundamentals(
                    symbol=symbol, market_country=market_country,
                    market_price=market_price, shares_outstanding=shares_outstanding,
                )
            except FundamentalsError as exc:
                st.error(str(exc))
                return
        try:
            save_fundamental_result(
                engine, symbol=symbol, market_country=market_country, result=result
            )
        except SQLAlchemyError:
            st.warning("재무정보 저장에는 실패했지만 조회 결과는 계속 표시합니다.")
        show_fundamentals_dialog(name, symbol, result)


@st.dialog("기업가치·재무제표", width="small")
def show_fundamentals_dialog(name: str, symbol: str, result: FundamentalResult) -> None:
    safe_name, safe_symbol = escape(name), escape(symbol)
    roe = "자료 없음" if result.roe_pct is None else f"{result.roe_pct:,.1f}%"
    liability_pct = (result.liabilities / result.assets * 100) if result.liabilities is not None and result.assets else 0
    equity_pct = (result.equity / result.assets * 100) if result.equity is not None and result.assets else 0
    liability_pct = max(0, min(100, liability_pct))
    equity_pct = max(0, min(100, equity_pct))
    st.markdown(f"""
    <style>
      .fv-hero{{display:flex;align-items:center;gap:14px;padding:16px;border-radius:18px;background:linear-gradient(135deg,#fff4f2,#f3f7ff);margin-bottom:12px}}
      .fv-hero svg{{width:48px;height:48px;flex:none}} .fv-hero h3{{margin:0;font-size:21px}} .fv-hero p{{margin:3px 0 0;color:#7a8290;font-size:12px}}
      .fv-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin:10px 0}}
      .fv-card{{border:1px solid #e9eaf0;border-radius:14px;padding:11px;background:#fff;min-width:0}}
      .fv-card small{{color:#777f8c;font-size:11px}} .fv-card b{{display:block;font-size:20px;margin:3px 0;color:#252936;white-space:nowrap}}
      .fv-card em{{font-style:normal;color:#9a9faa;font-size:10px;line-height:1.25;display:block}}
      .fv-section{{font-weight:750;font-size:14px;margin:18px 0 8px}}
      .fv-flow{{background:#f8f9fc;border-radius:14px;padding:12px}}
      .fv-row{{display:grid;grid-template-columns:68px 1fr 82px;align-items:center;gap:8px;margin:9px 0;font-size:12px}}
      .fv-track{{height:9px;border-radius:9px;background:#e9edf4;overflow:hidden}} .fv-fill{{height:100%;border-radius:9px;background:linear-gradient(90deg,#ff8f86,#ef5f68)}}
      .fv-money{{text-align:right;font-weight:700;white-space:nowrap}}
      .fv-balance{{display:flex;height:18px;border-radius:10px;overflow:hidden;margin:9px 0 6px;background:#edf0f5}}
      .fv-debt{{background:#9bc7f5}} .fv-equity{{background:#f5a7ad}} .fv-legend{{display:flex;justify-content:space-between;color:#687180;font-size:11px}}
      .fv-cash{{display:flex;align-items:center;justify-content:space-between;padding:11px 13px;border-radius:13px;background:#f2f8f5;margin-top:10px}}
      .fv-cash span{{font-size:12px;color:#56645c}} .fv-cash b{{font-size:16px;color:#287653}}
    </style>
    <div class="fv-hero">
      <svg viewBox="0 0 64 64" aria-hidden="true"><rect x="7" y="27" width="12" height="27" rx="3" fill="#f7a4aa"/><rect x="26" y="17" width="12" height="37" rx="3" fill="#ff7e86"/><rect x="45" y="7" width="12" height="47" rx="3" fill="#e75560"/><path d="M10 20 28 10l12 5L55 3" fill="none" stroke="#415170" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/></svg>
      <div><h3>{safe_name}</h3><p>{safe_symbol} · {result.fiscal_year}년 연간 · {result.provider} · {result.statement_type}</p></div>
    </div>
    <div class="fv-grid">
      <div class="fv-card"><small>PER · 이익 기준</small><b>{_multiple(result.per_ratio)}</b><em>현재 기업가치가 연간 순이익의 몇 배인지</em></div>
      <div class="fv-card"><small>PBR · 자본 기준</small><b>{_multiple(result.pbr_ratio)}</b><em>현재 기업가치가 장부상 자본의 몇 배인지</em></div>
      <div class="fv-card"><small>PSR · 매출 기준</small><b>{_multiple(result.psr_ratio)}</b><em>현재 기업가치가 연간 매출의 몇 배인지</em></div>
    </div>
    <div class="fv-card"><small>ROE · 자본 효율</small><b>{roe}</b><em>자본을 활용해 얼마만큼 순이익을 냈는지</em></div>
    <div class="fv-section">매출이 이익으로 남는 과정</div>
    <div class="fv-flow">
      <div class="fv-row"><span>매출</span><div class="fv-track"><div class="fv-fill" style="width:100%"></div></div><span class="fv-money">{_money(result.revenue,result.currency)}</span></div>
      <div class="fv-row"><span>영업이익</span><div class="fv-track"><div class="fv-fill" style="width:{_ratio_width(result.operating_income,result.revenue):.1f}%"></div></div><span class="fv-money">{_money(result.operating_income,result.currency)}</span></div>
      <div class="fv-row"><span>순이익</span><div class="fv-track"><div class="fv-fill" style="width:{_ratio_width(result.net_income,result.revenue):.1f}%"></div></div><span class="fv-money">{_money(result.net_income,result.currency)}</span></div>
    </div>
    <div class="fv-section">회사의 자산은 어떻게 구성됐을까?</div>
    <div class="fv-card"><small>총자산 {_money(result.assets,result.currency)}</small>
      <div class="fv-balance"><div class="fv-debt" style="width:{liability_pct:.1f}%"></div><div class="fv-equity" style="width:{equity_pct:.1f}%"></div></div>
      <div class="fv-legend"><span>● 부채 {liability_pct:.1f}% · {_money(result.liabilities,result.currency)}</span><span>● 자본 {equity_pct:.1f}% · {_money(result.equity,result.currency)}</span></div>
    </div>
    <div class="fv-cash"><span>💧 영업으로 들어온 현금</span><b>{_money(result.operating_cash_flow,result.currency)}</b></div>
    """, unsafe_allow_html=True)
    for limitation in result.limitations:
        st.caption(f"• {limitation}")
    st.link_button("공식 공시에서 확인", result.source_url, use_container_width=True)
    st.caption("정보 제공 목적이며 투자 권유나 수익 보장이 아닙니다.")
