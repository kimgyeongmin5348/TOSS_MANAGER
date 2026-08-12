"""Toss Securities portfolio and stock explorer."""
from __future__ import annotations

import re
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from toss_manager.client import TossAPIClient, TossAPIError
from toss_manager.config import Settings
from toss_manager.transform import candles_frame, holdings_frame

st.set_page_config(page_title="Porto | 투자 포트폴리오", page_icon="📈", layout="wide", initial_sidebar_state="expanded")

CSS = """<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Noto+Sans+KR:wght@400;500;600;700&display=swap');
:root{--blue:#2864dc;--red:#e5484d;--ink:#161b26;--muted:#717784;--line:#e8ebf0}
.stApp{background:#f7f8fb;color:var(--ink);font-family:Inter,'Noto Sans KR',sans-serif}.block-container{max-width:1240px;padding:4.25rem 2rem 4rem!important}
[data-testid=stSidebar]{background:#fff;border-right:1px solid var(--line)}[data-testid=stSidebar] .block-container{padding:1.35rem 1rem}.brand{display:flex;align-items:center;gap:.6rem;font-weight:700;font-size:1.15rem;margin:.2rem 0 1.5rem}.mark{display:grid;place-items:center;width:32px;height:32px;border-radius:10px;color:#fff;background:var(--blue)}
.side-title{font-size:.73rem;font-weight:700;color:#959baa;letter-spacing:.08em;margin:1.25rem 0 .45rem}.holding{padding:.75rem .2rem;border-bottom:1px solid #f0f2f5}.holding-top{display:flex;justify-content:space-between;gap:.4rem}.holding-name{font-size:.82rem;font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.holding-rate{font-size:.77rem;font-weight:600;color:var(--blue)}.negative{color:var(--red)!important}.holding-meta{display:flex;justify-content:space-between;margin-top:.25rem;color:var(--muted);font-size:.68rem}.page-head{display:flex;align-items:end;justify-content:space-between;margin-bottom:1.2rem}.page-head h1{font-size:1.75rem;letter-spacing:-.04em;margin:0}.page-head p{color:var(--muted);font-size:.82rem;margin:.35rem 0 0}.card{background:#fff;border:1px solid var(--line);border-radius:18px;padding:1.35rem;box-shadow:0 7px 24px rgba(20,30,50,.035)}
.rank-row{display:grid;grid-template-columns:38px 1fr 100px 100px 115px;align-items:center;padding:.82rem .4rem;border-bottom:1px solid #f0f2f5;font-size:.82rem}.rank-row:last-child{border:0}.rank{color:#9198a5;font-weight:600}.sym{font-weight:700}.sub{font-size:.68rem;color:var(--muted);margin-top:.15rem}.num{text-align:right;font-variant-numeric:tabular-nums}.rate{color:var(--blue);font-weight:600}.stock-head{display:flex;align-items:center;justify-content:space-between}.stock-head h2{margin:0;font-size:1.55rem}.price{font-size:1.5rem;font-weight:700;text-align:right}.caption{color:var(--muted);font-size:.75rem}.empty{padding:3rem;text-align:center;color:var(--muted)}
.stButton button{width:100%;border-radius:10px}.stTextInput input{border-radius:10px}@media(max-width:800px){.block-container{padding:1rem}.rank-row{grid-template-columns:32px 1fr 80px 80px}.rank-row>:nth-child(4){display:none}}
.login-shell{min-height:72vh;display:flex;flex-direction:column;justify-content:center}.login-kicker{display:inline-flex;align-items:center;gap:.5rem;color:var(--blue);background:#edf3ff;border-radius:99px;padding:.45rem .75rem;font-size:.72rem;font-weight:700;letter-spacing:.04em}.login-title{font-size:3.35rem;line-height:1.13;letter-spacing:-.065em;margin:1.15rem 0 1rem;max-width:650px}.login-copy{font-size:1rem;line-height:1.8;color:var(--muted);max-width:560px}.feature-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:.7rem;margin-top:2rem;max-width:620px}.feature{background:#fff;border:1px solid var(--line);border-radius:15px;padding:1rem}.feature-icon{display:grid;place-items:center;width:30px;height:30px;border-radius:9px;background:#f0f4ff;color:var(--blue);font-size:.8rem;font-weight:700}.feature strong{display:block;font-size:.78rem;margin:.7rem 0 .2rem}.feature small{font-size:.67rem;color:var(--muted);line-height:1.45}.login-card{background:#fff;border:1px solid var(--line);border-radius:24px;padding:1.8rem;box-shadow:0 20px 55px rgba(25,42,75,.09);margin-top:2rem}.login-card-head{display:flex;align-items:center;gap:.8rem;margin-bottom:1.35rem}.login-logo{display:grid;place-items:center;width:42px;height:42px;border-radius:13px;background:#edf3ff;color:var(--blue);font-weight:800}.login-card h3{margin:0;font-size:1.08rem}.login-card p{margin:.2rem 0 0;color:var(--muted);font-size:.72rem}.secure-note{display:flex;gap:.55rem;align-items:flex-start;background:#f7f9fc;border-radius:12px;padding:.8rem;margin-top:.9rem;color:#687083;font-size:.68rem;line-height:1.5}.steps{display:flex;justify-content:center;gap:.65rem;margin-top:1.3rem;color:#9aa0ab;font-size:.66rem}.steps b{color:var(--blue)}.login-help{text-align:center;color:var(--muted);font-size:.69rem;margin-top:1rem}.login-help a{color:var(--blue);text-decoration:none}.login-card [data-testid=stFormSubmitButton] button{height:47px;background:var(--blue);color:#fff;border:0;font-weight:700}.login-card [data-testid=stTextInput] label{font-size:.75rem;font-weight:600}.login-card [data-testid=stTextInput] input{height:46px;background:#fbfcfe;border-color:#e2e6ed}@media(max-width:800px){.login-shell{min-height:auto}.login-title{font-size:2.4rem}.feature-grid{grid-template-columns:1fr}.login-card{margin-top:1rem}}
.login-shell{min-height:66vh!important}
.brand-story{display:flex;align-items:center;gap:.65rem;margin-top:1.15rem;color:#4f596b;font-size:.76rem}.brand-story b{color:var(--ink);font-size:.83rem}.brand-story i{width:1px;height:14px;background:#cfd4dd}.feature-grid{margin-top:1.5rem!important}
@media(max-width:800px){.block-container{padding:3.5rem 1rem 3rem!important}}
</style>"""

PERIODS = {"1분": ("1m", None, 120), "5분": ("1m", "5min", 200), "10분": ("1m", "10min", 200), "1일": ("1d", None, 120), "주": ("1d", "W-FRI", 200), "월": ("1d", "ME", 200), "년": ("1d", "YE", 200)}

def currency(value: float, market: str) -> str:
    return f"${value:,.2f}" if market == "US" else f"₩{value:,.0f}"

def connect_view() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    st.markdown('<div class="brand"><span class="mark">P</span>porto <span style="margin-left:auto;font-size:.7rem;color:#9299a7;font-weight:500">PORTFOLIO INTELLIGENCE</span></div>', unsafe_allow_html=True)
    a, b = st.columns([1.18, .82], gap="large", vertical_alignment="center")
    with a:
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
    with b:
        st.markdown('<div class="login-card"><div class="login-card-head"><span class="login-logo">T</span><div><h3>토스증권 계좌 연결</h3><p>Open API 키로 안전하게 시작하세요.</p></div></div>', unsafe_allow_html=True)
        with st.form("connect", border=False):
            cid = st.text_input("Client ID", placeholder="발급받은 Client ID")
            secret = st.text_input("Client Secret", type="password", placeholder="발급받은 Client Secret")
            submit = st.form_submit_button("안전하게 계좌 연결하기  →", use_container_width=True)
        st.markdown('''<div class="secure-note"><span>🔒</span><span><b>읽기 전용으로 연결돼요.</b><br>입력한 키는 데이터베이스에 저장하지 않으며 주문 권한을 사용하지 않습니다.</span></div>
        <div class="steps"><b>1. API 키 입력</b><span>—</span><span>2. 계좌 확인</span><span>—</span><span>3. 분석 시작</span></div>
        <div class="login-help">API 키가 없나요? 토스증권 WTS의 <a href="https://developers.tossinvest.com/docs" target="_blank">Open API 설정 안내</a>를 확인하세요.</div></div>''', unsafe_allow_html=True)
        if submit:
            if not cid.strip() or not secret.strip(): st.error("두 항목을 모두 입력해 주세요."); return
            try:
                client = TossAPIClient(Settings(cid.strip(), secret.strip()))
                accounts = client.get_accounts()
                if not accounts: st.warning("조회 가능한 계좌가 없습니다."); return
                st.session_state.client, st.session_state.accounts = client, accounts
                st.rerun()
            except (TossAPIError, ValueError, KeyError) as exc:
                st.error(f"연결에 실패했습니다: {exc}")

def aggregate_candles(df: pd.DataFrame, rule: str | None) -> pd.DataFrame:
    if df.empty or not rule: return df
    indexed = df.set_index("timestamp")
    return indexed.resample(rule).agg(open_price=("open_price", "first"), high_price=("high_price", "max"), low_price=("low_price", "min"), close_price=("close_price", "last"), volume=("volume", "sum")).dropna(subset=["open_price", "close_price"]).reset_index()

def load_holdings(client: TossAPIClient, accounts: list[dict]) -> tuple[pd.DataFrame, int]:
    labels = {f"{a.get('accountNo', '계좌')} · {a.get('accountType', '')}": int(a["accountSeq"]) for a in accounts}
    selected = st.sidebar.selectbox("계좌", labels)
    seq = labels[selected]
    return holdings_frame(client.get_holdings(seq), seq), seq

def sidebar(df: pd.DataFrame) -> None:
    st.sidebar.markdown('<div class="side-title">MY HOLDINGS</div>', unsafe_allow_html=True)
    if df.empty: st.sidebar.caption("보유 종목이 없습니다.")
    for x in df.itertuples():
        rate = float(x.profit_loss_rate or 0); tone = "negative" if rate < 0 else ""
        market = "US" if str(x.currency) == "USD" else "KR"
        qty = float(x.quantity or 0); qty_text = f"{qty:,.4f}".rstrip("0").rstrip(".")
        st.sidebar.markdown(f'<div class="holding"><div class="holding-top"><span class="holding-name">{x.name or x.symbol}</span><span class="holding-rate {tone}">{rate:+.2f}%</span></div><div class="holding-meta"><span>{x.symbol} · {qty_text}주</span><span>평단 {currency(float(x.average_purchase_price or 0), market)}</span></div></div>', unsafe_allow_html=True)
    st.sidebar.write("")
    if st.sidebar.button("연결 해제"):
        st.session_state.clear(); st.rerun()

def stock_detail(client: TossAPIClient, symbol: str, market: str, name: str | None = None) -> None:
    try:
        info = client.get_stocks([symbol])
        info = info[0] if info else {}
        name = info.get("name") or name or symbol
        prices = client.get_prices([symbol]); price = prices[0] if prices else {}
    except TossAPIError as exc:
        st.error(f"종목 정보를 불러오지 못했습니다: {exc}"); return
    last = float(price.get("lastPrice") or 0)
    st.markdown(f'<div class="card"><div class="stock-head"><div><h2>{name}</h2><div class="caption">{symbol} · {"미국" if market == "US" else "한국"}</div></div><div><div class="price">{currency(last, market)}</div><div class="caption">현재가</div></div></div></div>', unsafe_allow_html=True)
    st.write("")
    period = st.segmented_control("캔들 주기", list(PERIODS), default="1일")
    api_interval, rule, count = PERIODS[period or "1일"]
    try:
        raw = client.get_candles(symbol, interval=api_interval, count=count)
        df = aggregate_candles(candles_frame(raw, symbol, api_interval), rule)
        if df.empty: st.info("표시할 차트 데이터가 없습니다."); return
        fig = go.Figure(go.Candlestick(x=df.timestamp, open=df.open_price, high=df.high_price, low=df.low_price, close=df.close_price, increasing_line_color="#e5484d", increasing_fillcolor="#e5484d", decreasing_line_color="#2864dc", decreasing_fillcolor="#2864dc", name=symbol))
        fig.update_layout(height=560, margin=dict(l=10,r=10,t=25,b=10), xaxis_rangeslider_visible=False, paper_bgcolor="white", plot_bgcolor="white", yaxis=dict(side="right", gridcolor="#eef0f4", tickprefix="$" if market == "US" else "₩"), xaxis=dict(gridcolor="#f3f4f6"), showlegend=False)
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        if period in {"5분", "10분", "주", "월", "년"}: st.caption(f"공식 {api_interval} 데이터를 {period} 단위로 집계한 차트입니다.")
    except (TossAPIError, ValueError) as exc: st.error(f"차트 데이터를 불러오지 못했습니다: {exc}")

def market_view(client: TossAPIClient) -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    market_label = st.segmented_control("시장", ["미장", "국장"], default="미장")
    market = "US" if market_label == "미장" else "KR"
    st.markdown(f'<div class="page-head"><div><h1>{market_label} 거래량 순위</h1><p>실시간 시장 거래량 기준 · 상위 50개 종목</p></div></div>', unsafe_allow_html=True)
    with st.form("search", clear_on_submit=False):
        c1, c2 = st.columns([5,1])
        query = c1.text_input("종목 검색", placeholder="티커 입력 (예: AAPL, TSLA)", label_visibility="collapsed")
        searched = c2.form_submit_button("검색", use_container_width=True)
    if searched:
        symbol = query.strip().upper()
        if not re.fullmatch(r"[A-Z0-9.\-]+", symbol): st.warning("올바른 종목 티커를 입력해 주세요.")
        else: st.session_state.selected_symbol = symbol; st.session_state.selected_market = market
    if st.session_state.get("selected_symbol") and st.session_state.get("selected_market") == market:
        if st.button("← 거래량 순위로 돌아가기"): st.session_state.pop("selected_symbol", None); st.rerun()
        stock_detail(client, st.session_state.selected_symbol, market); return
    try:
        payload = client.get_rankings(market, count=50); rankings = payload.get("rankings", [])
    except (TossAPIError, ValueError) as exc: st.error(f"거래량 순위를 불러오지 못했습니다: {exc}"); return
    if not rankings: st.markdown('<div class="card empty">현재 집계된 거래량 순위가 없습니다.</div>', unsafe_allow_html=True); return
    symbols = [x["symbol"] for x in rankings]
    try: stocks = {x["symbol"]: x for x in client.get_stocks(symbols)}
    except TossAPIError: stocks = {}
    st.markdown('<div class="card">', unsafe_allow_html=True)
    for item in rankings:
        symbol=item["symbol"]; p=item.get("price",{}); last=float(p.get("lastPrice") or 0); rate=float(p.get("changeRate") or 0)*100; volume=float(item.get("tradingVolume") or 0); tone="negative" if rate<0 else ""; name=stocks.get(symbol,{}).get("name",symbol)
        c1,c2=st.columns([7,1])
        c1.markdown(f'<div class="rank-row"><span class="rank">{item.get("rank","")}</span><span><span class="sym">{name}</span><div class="sub">{symbol}</div></span><span class="num">{currency(last,market)}</span><span class="num rate {tone}">{rate:+.2f}%</span><span class="num">{volume:,.0f}주</span></div>', unsafe_allow_html=True)
        if c2.button("보기", key=f"rank_{market}_{symbol}"):
            st.session_state.selected_symbol=symbol; st.session_state.selected_market=market; st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

def main() -> None:
    if "client" not in st.session_state: connect_view(); return
    client=st.session_state.client
    st.sidebar.markdown('<div class="brand"><span class="mark">P</span>porto</div>', unsafe_allow_html=True)
    try: holdings,_=load_holdings(client,st.session_state.accounts)
    except TossAPIError as exc: st.error(f"계좌를 불러오지 못했습니다: {exc}"); return
    sidebar(holdings); market_view(client)

if __name__ == "__main__": main()
