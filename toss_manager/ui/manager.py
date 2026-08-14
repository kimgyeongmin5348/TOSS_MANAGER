"""Porto Manager analysis dialog."""

from hashlib import sha256
from html import escape

import pandas as pd
import streamlit as st
from sqlalchemy import Engine
from sqlalchemy.exc import SQLAlchemyError

from toss_manager.analysis import analyze_candles
from toss_manager.llm import (
    NvidiaLLMClient,
    NvidiaLLMError,
    build_llm_messages,
    build_symbol_manager_context,
)
from toss_manager.news import sync_symbol_news
from toss_manager.news.models import NewsSyncResult
from toss_manager.ui.disclaimer import render_investment_disclaimer


@st.fragment(run_every="60s")
def render_manager_launcher(
    engine: Engine,
    *,
    name: str,
    symbol: str,
    market_country: str,
    candles: pd.DataFrame,
    period: str,
    return_threshold: float,
    offline: bool = False,
) -> None:
    """Refresh news every minute while the stock detail remains open."""
    try:
        news_result = sync_symbol_news(
            engine,
            symbol=symbol,
            name=name,
            market_country=market_country,
            period=period,
        )
    except (SQLAlchemyError, ValueError):
        news_result = None

    prefix = "저장 데이터로 " if offline else ""
    if st.button(
        f"✦ {prefix}Porto 매니저 · 다음 {period}봉",
        use_container_width=True,
        key=f"manager_{'offline' if offline else 'live'}_{market_country}_{symbol}_{period}",
    ):
        show_manager_dialog(
            name,
            symbol,
            candles,
            period=period,
            return_threshold=return_threshold,
            news_result=news_result,
            market_country=market_country,
            offline=offline,
        )


def _palette(direction: str) -> tuple[str, str, str, str]:
    if "상승" in direction:
        return "상승", "#e85d68", "#fff0f1", "↗"
    if "하락" in direction:
        return "하락", "#4d86d9", "#eef6ff", "↘"
    return "보합", "#7773b9", "#f3f1ff", "→"


def _analysis_cache_key(
    *,
    market_country: str,
    symbol: str,
    period: str,
    result: object,
    news_result: NewsSyncResult | None,
) -> str:
    """Create a stable key so rerenders do not repeat a paid/external LLM call."""
    news = news_result.summary if news_result else None
    raw = "|".join(
        (
            "prompt-v2",
            market_country,
            symbol,
            period,
            str(result.score),
            str(result.candle_count),
            str(result.analyzed_at),
            str(news.score if news else "none"),
            str(news.latest_at if news else "none"),
        )
    )
    return f"porto_comment_{sha256(raw.encode('utf-8')).hexdigest()[:20]}"


def _render_styles() -> None:
    st.markdown(
        """
        <style>
        .porto-hero{padding:17px 18px;border-radius:22px;margin:4px 0 12px;
          display:flex;align-items:center;justify-content:space-between;gap:14px}
        .porto-kicker{font-size:.72rem;font-weight:800;letter-spacing:.08em;opacity:.63}
        .porto-direction{font-size:1.55rem;font-weight:900;line-height:1.2;margin:4px 0}
        .porto-sub{font-size:.76rem;color:#667085}
        .porto-gauge{width:84px;height:84px;border-radius:50%;display:grid;place-items:center;
          position:relative;flex:0 0 84px}
        .porto-gauge:after{content:"";position:absolute;inset:8px;border-radius:50%;background:white}
        .porto-gauge strong{position:relative;z-index:1;font-size:1.22rem;color:#202738}
        .porto-comment{padding:15px 16px;border:1px solid #e5e9f1;border-radius:18px;
          background:linear-gradient(135deg,#faf7ff,#f6f9ff);margin:8px 0 14px}
        .porto-comment-title{font-weight:900;color:#292448;margin-bottom:7px}
        .porto-comment-body{font-size:.88rem;line-height:1.62;color:#34384a}
        .porto-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:7px;margin:9px 0}
        .porto-stat{padding:11px 7px;border:1px solid #eaecf1;border-radius:14px;background:#fff;text-align:center}
        .porto-stat small{display:block;color:#858b98;font-size:.67rem;margin-bottom:3px}
        .porto-stat b{font-size:1.02rem;color:#292d3b}
        .porto-bar{height:9px;border-radius:99px;overflow:hidden;display:flex;background:#edf0f4;margin:10px 0 5px}
        .porto-bar span{height:100%}
        .porto-legend{display:flex;justify-content:space-between;color:#7a808d;font-size:.68rem}
        .porto-evidence{display:grid;grid-template-columns:30px 1fr auto;gap:9px;align-items:center;
          padding:10px 11px;border:1px solid #eaedf2;border-radius:14px;margin:7px 0;background:#fff}
        .porto-evidence-icon{width:29px;height:29px;border-radius:10px;display:grid;place-items:center;font-weight:900}
        .porto-evidence b{display:block;font-size:.79rem;color:#303442}
        .porto-evidence small{font-size:.69rem;color:#7d8390;line-height:1.35}
        .porto-points{font-size:.72rem;font-weight:800;color:#6a7080}
        .porto-news{padding:13px 14px;border-radius:17px;border:1px solid #e8ebf1;margin:8px 0;background:#fbfcfe}
        .porto-news-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:7px}
        .porto-news-head b{font-size:.9rem}.porto-news-score{font-size:1.15rem;font-weight:900}
        .porto-news-meta{font-size:.71rem;color:#777e8b;line-height:1.55}
        @media(max-width:420px){.porto-grid{grid-template-columns:repeat(3,1fr)}.porto-hero{padding:14px}}
        </style>
        """,
        unsafe_allow_html=True,
    )


def _porto_comment(
    *, name: str, symbol: str, market_country: str, period: str,
    result: object, news_result: NewsSyncResult | None, offline: bool,
) -> tuple[str | None, str | None, bool]:
    client = NvidiaLLMClient()
    if not client.configured:
        return None, None, False

    cache_key = _analysis_cache_key(
        market_country=market_country, symbol=symbol, period=period,
        result=result, news_result=news_result,
    )
    cached = st.session_state.get(cache_key)
    if isinstance(cached, dict):
        return cached.get("answer"), cached.get("error"), True

    context = build_symbol_manager_context(
        symbol=symbol,
        name=name,
        market_country=market_country,
        period=period,
        analysis=result,
        news=news_result,
        offline=offline,
        data_as_of=result.analyzed_at,
    )
    question = (
        f"{name}의 다음 {period}봉 전망을 초보자도 이해할 수 있게 한국어 3문장으로 설명해줘. "
        "첫 문장은 결론, 둘째는 가장 중요한 근거, 셋째는 반드시 위험 요인으로 작성해줘."
    )
    try:
        with st.spinner("Porto가 차트와 뉴스를 함께 읽고 있어요…"):
            answer = client.complete(build_llm_messages(context, user_question=question))
        st.session_state[cache_key] = {"answer": answer, "error": None}
        return answer, None, True
    except NvidiaLLMError as exc:
        error = str(exc)
        st.session_state[cache_key] = {"answer": None, "error": error}
        return None, error, True


def _render_manager_question(
    *, name: str, symbol: str, market_country: str, period: str,
    result: object, news_result: NewsSyncResult | None, offline: bool,
) -> None:
    """Render an optional follow-up question without replacing the automatic comment."""
    client = NvidiaLLMClient()
    if not client.configured:
        return

    analysis_key = _analysis_cache_key(
        market_country=market_country,
        symbol=symbol,
        period=period,
        result=result,
        news_result=news_result,
    ).removeprefix("porto_comment_")
    question_key = f"porto_question_{market_country}_{symbol}_{period}"
    answer_key = f"porto_question_answer_v2_{analysis_key}"
    with st.form(
        key=f"porto_question_form_{market_country}_{symbol}_{period}",
        clear_on_submit=False,
    ):
        question = st.text_input(
            "Porto에게 더 물어보기",
            placeholder="예: 지금 가장 조심해야 할 위험은 뭐야?",
            key=question_key,
        )
        submitted = st.form_submit_button("질문하기", use_container_width=True)

    if submitted:
        clean_question = question.strip()
        if not clean_question:
            st.warning("궁금한 내용을 입력해 주세요.")
        else:
            context = build_symbol_manager_context(
                symbol=symbol,
                name=name,
                market_country=market_country,
                period=period,
                analysis=result,
                news=news_result,
                offline=offline,
                data_as_of=result.analyzed_at,
            )
            try:
                with st.spinner("Porto가 질문을 살펴보고 있어요…"):
                    answer = client.complete(
                        build_llm_messages(context, user_question=clean_question)
                    )
                st.session_state[answer_key] = {
                    "question": clean_question,
                    "answer": answer,
                }
            except NvidiaLLMError as exc:
                st.error(str(exc))

    response = st.session_state.get(answer_key)
    if isinstance(response, dict) and response.get("answer"):
        with st.container(border=True):
            st.markdown(f"##### Q. {response['question']}")
            st.markdown(response["answer"])


@st.dialog("Porto 매니저", width="small")
def show_manager_dialog(
    name: str,
    symbol: str,
    candles: pd.DataFrame,
    period: str = "1일",
    return_threshold: float = 0.002,
    news_result: NewsSyncResult | None = None,
    market_country: str = "US",
    offline: bool = False,
) -> None:
    _render_styles()
    try:
        result = analyze_candles(candles, return_threshold=return_threshold)
    except ValueError as exc:
        st.warning(str(exc))
        return

    label, accent, tint, arrow = _palette(result.direction)
    score = max(0, min(100, result.score))
    st.markdown(
        f"""
        <div class="porto-hero" style="background:{tint};border:1px solid {accent}30">
          <div><div class="porto-kicker">{escape(symbol)} · 다음 {escape(period)}봉</div>
          <div class="porto-direction" style="color:{accent}">{arrow} {escape(label)} 관점</div>
          <div class="porto-sub">{escape(name)} · 기술 지표와 과거 유사 신호 분석</div></div>
          <div class="porto-gauge" style="background:conic-gradient({accent} {score * 3.6}deg,#e7eaf0 0)">
            <strong>{score}점</strong></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    answer, ai_error, configured = _porto_comment(
        name=name, symbol=symbol, market_country=market_country, period=period,
        result=result, news_result=news_result, offline=offline,
    )
    if answer:
        with st.container(border=True):
            st.markdown("##### ✦ Porto의 한마디")
            st.markdown(answer)
    elif ai_error:
        st.markdown(
            '<div class="porto-comment"><div class="porto-comment-title">✦ Porto의 한마디</div>'
            '<div class="porto-comment-body">AI 설명을 잠시 불러오지 못했어요. 아래 수치 분석은 정상적으로 확인할 수 있습니다.</div></div>',
            unsafe_allow_html=True,
        )
    elif not configured:
        st.markdown(
            '<div class="porto-comment"><div class="porto-comment-title">✦ Porto의 한마디</div>'
            '<div class="porto-comment-body">NVIDIA_API_KEY를 설정하면 이곳에 차트·뉴스를 종합한 설명이 자동으로 표시됩니다.</div></div>',
            unsafe_allow_html=True,
        )

    _render_manager_question(
        name=name,
        symbol=symbol,
        market_country=market_country,
        period=period,
        result=result,
        news_result=news_result,
        offline=offline,
    )

    stats = result.backtest
    total = stats.rises + stats.falls + stats.flats
    rise_pct = stats.rises / total * 100 if total else 0
    fall_pct = stats.falls / total * 100 if total else 0
    flat_pct = max(0, 100 - rise_pct - fall_pct) if total else 100
    rise_rate = f"{stats.rise_rate:.1f}%" if stats.rise_rate is not None else "표본 부족"
    st.markdown(
        f"""
        <div class="porto-grid">
          <div class="porto-stat"><small>유사 신호</small><b>{stats.occurrences:,}회</b></div>
          <div class="porto-stat"><small>과거 상승률</small><b>{rise_rate}</b></div>
          <div class="porto-stat"><small>상승 / 하락</small><b>{stats.rises} / {stats.falls}</b></div>
        </div>
        <div class="porto-bar"><span style="width:{rise_pct:.1f}%;background:#ee7a82"></span>
          <span style="width:{flat_pct:.1f}%;background:#c8ccd5"></span>
          <span style="width:{fall_pct:.1f}%;background:#70a1e3"></span></div>
        <div class="porto-legend"><span>상승 {stats.rises}</span><span>보합 {stats.flats}</span><span>하락 {stats.falls}</span></div>
        """,
        unsafe_allow_html=True,
    )
    if stats.rise_rate is not None and stats.base_rise_rate is not None:
        st.caption(f"전체 기간 상승률 {stats.base_rise_rate:.1f}% 대비 {stats.rise_rate - stats.base_rise_rate:+.1f}%p")

    st.markdown("##### 왜 이렇게 봤나요?")
    for evidence in result.evidence:
        _, ev_accent, ev_tint, ev_arrow = _palette("상승" if evidence.state > 0 else "하락" if evidence.state < 0 else "보합")
        st.markdown(
            f'<div class="porto-evidence"><div class="porto-evidence-icon" style="background:{ev_tint};color:{ev_accent}">{ev_arrow}</div>'
            f'<div><b>{escape(evidence.label)}</b><small>{escape(evidence.description)}</small></div>'
            f'<div class="porto-points">{evidence.points:g}/{evidence.maximum:g}</div></div>',
            unsafe_allow_html=True,
        )

    st.markdown("##### 뉴스 온도")
    if news_result is None or (
        not news_result.active_providers and news_result.summary.article_count == 0
    ):
        st.caption("연결된 뉴스가 없어 이번 결과에는 차트 신호만 반영했습니다.")
    else:
        news = news_result.summary
        _, news_accent, news_tint, _ = _palette(
            "상승" if news.direction == "긍정" else "하락" if news.direction == "부정" else "보합"
        )
        providers = ", ".join(news_result.active_providers) or "저장된 뉴스"
        st.markdown(
            f'<div class="porto-news" style="background:{news_tint}"><div class="porto-news-head">'
            f'<b>{escape(news.direction)} 분위기</b><span class="porto-news-score" style="color:{news_accent}">{news.score}점</span></div>'
            f'<div class="porto-news-meta">관련 기사·공시 {news.article_count}건 · 신뢰도 {news.confidence}점 · {escape(providers)}<br>'
            f'긍정 {news.positive_count} · 중립 {news.neutral_count} · 부정 {news.negative_count} · 방향 일치도 {news.agreement}%</div></div>',
            unsafe_allow_html=True,
        )
        with st.expander("뉴스 점수 기준과 근거"):
            for reason in news.reasons:
                st.caption(f"• {reason}")
            for explanation in news.methodology:
                st.caption(f"• {explanation}")

    render_investment_disclaimer(compact=True)
    source = "저장 데이터" if offline else "조회 데이터"
    st.caption(f"{source} · 캔들 {result.candle_count:,}개 · 기준 {result.analyzed_at}")
