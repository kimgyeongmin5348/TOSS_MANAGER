"""Collect configured news providers and build a period-aware sentiment summary."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from functools import lru_cache

from sqlalchemy import Engine

from toss_manager.config import NewsSettings

from .models import NewsSummary, NewsSyncResult
from .providers import (
    AlphaVantageNewsProvider,
    NaverNewsProvider,
    NewsProviderError,
    OpenDartProvider,
)
from .repository import (
    latest_collection_at,
    load_recent_news,
    mark_collection_success,
    upsert_news_articles,
)


NEWS_WINDOWS = {
    "1분": timedelta(minutes=30),
    "5분": timedelta(hours=2),
    "10분": timedelta(hours=4),
    "1일": timedelta(days=3),
    "주": timedelta(days=14),
    "월": timedelta(days=60),
    "년": timedelta(days=60),
}

POSITIVE_EVENTS = {
    "실적 상회": 18, "어닝 서프라이즈": 18, "흑자 전환": 18,
    "영업익 증가": 12, "영업이익 증가": 12, "사상 최대": 12,
    "신규 계약": 12, "공급 계약": 12, "수주": 10, "승인": 10,
    "자사주 매입": 8, "배당 확대": 8, "목표가 상향": 8,
    "record revenue": 12, "earnings beat": 18, "upgrade": 8, "approval": 10,
}
NEGATIVE_EVENTS = {
    "실적 하회": 18, "어닝 쇼크": 18, "적자 전환": 18,
    "영업익 감소": 12, "영업이익 감소": 12, "가이던스 하향": 15,
    "유상증자": 12, "소송": 8, "리콜": 12, "상장폐지": 25,
    "목표가 하향": 8, "earnings miss": 18, "downgrade": 8,
    "offering": 12, "lawsuit": 8, "recall": 12,
}


def sync_symbol_news(
    engine: Engine,
    *,
    symbol: str,
    name: str,
    market_country: str,
    period: str,
    settings: NewsSettings | None = None,
    now: datetime | None = None,
) -> NewsSyncResult:
    settings = settings or NewsSettings.from_env()
    now = now or datetime.now(timezone.utc)
    providers = _configured_providers(settings, market_country)
    errors = []
    active = []
    for provider_name, provider in providers:
        active.append(provider_name)
        last_at = latest_collection_at(
            engine, symbol=symbol, market_country=market_country, provider=provider_name
        )
        if last_at is not None:
            last_utc = last_at.replace(tzinfo=timezone.utc) if last_at.tzinfo is None else last_at.astimezone(timezone.utc)
            if now - last_utc < timedelta(seconds=settings.refresh_seconds):
                continue
        try:
            articles = provider.fetch(symbol, name)
            upsert_news_articles(
                engine,
                symbol=symbol,
                market_country=market_country,
                articles=articles,
            )
            mark_collection_success(
                engine,
                symbol=symbol,
                market_country=market_country,
                provider=provider_name,
            )
        except (NewsProviderError, ValueError) as exc:
            errors.append(str(exc))

    stored = load_recent_news(
        engine, symbol=symbol, market_country=market_country
    )
    return NewsSyncResult(
        summary=summarize_news(
            stored, period=period, now=now, symbol=symbol, name=name
        ),
        active_providers=tuple(active),
        errors=tuple(errors),
    )


def summarize_news(
    articles: list[dict],
    *,
    period: str,
    now: datetime | None = None,
    symbol: str = "",
    name: str = "",
) -> NewsSummary:
    now = now or datetime.now(timezone.utc)
    window = NEWS_WINDOWS.get(period, timedelta(days=3))
    cutoff = now - window
    relevant = []
    for article in articles:
        published_at = article["published_at"]
        published_utc = published_at.replace(tzinfo=timezone.utc) if published_at.tzinfo is None else published_at.astimezone(timezone.utc)
        if cutoff <= published_utc <= now:
            relevant.append((article, published_utc))
    if not relevant:
        return NewsSummary(
            "정보 없음", 50, 0, 0,
            ("분석 구간에 해당하는 뉴스가 없습니다.",), None,
            0, 0, 0, 0, 0, 0,
            ("현재 차트 주기의 뉴스 시간 범위 안에 있는 기사만 사용합니다.",),
        )

    weighted_total = 0.0
    total_weight = 0.0
    reasons = []
    scored = []
    excluded_count = 0
    for article, published_at in relevant:
        text = f"{article.get('title', '')} {article.get('summary', '')}".lower()
        provider_score = article.get("sentiment_score")
        if provider_score is not None:
            score = max(0.0, min(100.0, (float(provider_score) + 1.0) * 50.0))
        else:
            score = 50.0
            score += sum(points for word, points in POSITIVE_EVENTS.items() if word.lower() in text)
            score -= sum(points for word, points in NEGATIVE_EVENTS.items() if word.lower() in text)
            score = max(0.0, min(100.0, score))

        relevance = _article_relevance(article, symbol=symbol, name=name)
        if relevance < 0.35:
            excluded_count += 1
            continue
        age_ratio = max(0.0, min(1.0, (now - published_at).total_seconds() / window.total_seconds()))
        recency = 1.0 - age_ratio * 0.5
        source_weight = 1.15 if article.get("content_type") == "DISCLOSURE" else 1.0
        weight = relevance * recency * source_weight
        if article.get("content_type") == "DISCLOSURE":
            relevance = 1.0
        weighted_total += score * weight
        total_weight += weight
        scored.append((score, weight, relevance, article))
        if score >= 60 or score <= 40:
            reasons.append(f"{article.get('source')}: {article.get('title')}")
    if not scored:
        return NewsSummary(
            "정보 없음", 50, 0, 0,
            ("종목과 직접 관련된 뉴스가 없습니다.",), None,
            0, 0, 0, excluded_count, 0, 0,
            ("제목·요약에 종목명이나 티커가 확인되는 기사만 반영합니다.",),
        )

    score = round(weighted_total / total_weight)
    direction = "긍정" if score >= 60 else "부정" if score <= 40 else "중립"
    positive_count = sum(value >= 60 for value, *_ in scored)
    negative_count = sum(value <= 40 for value, *_ in scored)
    neutral_count = len(scored) - positive_count - negative_count
    average_relevance = round(
        sum(value[2] * value[1] for value in scored) / total_weight * 100
    )
    dispersion = sum(abs(value - score) * weight for value, weight, *_ in scored) / total_weight
    agreement = max(0, round(100 - dispersion * 2))
    coverage = min(100, len(scored) * 10)
    official_bonus = min(100, sum(
        article.get("content_type") == "DISCLOSURE" for *_, article in scored
    ) * 25)
    confidence = round(
        average_relevance * 0.4 + agreement * 0.3
        + coverage * 0.2 + official_bonus * 0.1
    )
    if not reasons:
        reasons.append("강한 긍정·부정 신호 없이 중립적인 뉴스 흐름입니다.")
    latest_at = max(published_at for _, published_at in relevant)
    methodology = (
        "기사별 50점에서 긍정 이벤트는 +8~+18점, 부정 이벤트는 -8~-25점을 반영합니다.",
        "종목 직접 관련성 × 최신성 × 출처 신뢰도로 기사별 가중치를 계산합니다.",
        "60점 이상 긍정, 40점 이하 부정, 그 사이는 중립입니다.",
        "신뢰도는 관련성 40% + 기사 간 일치도 30% + 표본 20% + 공식 공시 10%입니다.",
    )
    return NewsSummary(
        direction, score, confidence, len(scored), tuple(reasons[:3]), latest_at,
        positive_count, neutral_count, negative_count, excluded_count,
        average_relevance, agreement, methodology,
    )


def _article_relevance(article: dict, *, symbol: str, name: str) -> float:
    supplied = article.get("relevance_score")
    if supplied is not None:
        return max(0.0, min(1.0, float(supplied)))
    if article.get("content_type") == "DISCLOSURE":
        return 1.0
    title = str(article.get("title", "")).lower().replace(" ", "")
    summary = str(article.get("summary", "")).lower().replace(" ", "")
    identifiers = [
        value.lower().replace(" ", "")
        for value in (symbol, name)
        if value and len(value.strip()) >= 2
    ]
    if not identifiers:
        return 0.6
    if any(value in title for value in identifiers):
        return 1.0
    if any(value in summary for value in identifiers):
        return 0.55
    return 0.2


def _configured_providers(settings: NewsSettings, market_country: str):
    country = market_country.upper()
    providers = []
    if country == "KR":
        if settings.naver_client_id and settings.naver_client_secret:
            providers.append(("NAVER", _naver(settings.naver_client_id, settings.naver_client_secret)))
        if settings.opendart_api_key:
            providers.append(("OPENDART", _dart(settings.opendart_api_key)))
    elif country == "US" and settings.alpha_vantage_api_key:
        providers.append(("ALPHA_VANTAGE", _alpha(settings.alpha_vantage_api_key)))
    return providers


@lru_cache(maxsize=4)
def _naver(client_id: str, client_secret: str):
    return NaverNewsProvider(client_id, client_secret)


@lru_cache(maxsize=2)
def _dart(api_key: str):
    return OpenDartProvider(api_key)


@lru_cache(maxsize=2)
def _alpha(api_key: str):
    return AlphaVantageNewsProvider(api_key)
