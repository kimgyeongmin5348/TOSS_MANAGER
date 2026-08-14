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

POSITIVE_WORDS = (
    "실적 상회", "흑자 전환", "신규 계약", "수주", "승인", "자사주 매입",
    "배당 확대", "record revenue", "earnings beat", "upgrade", "approval",
)
NEGATIVE_WORDS = (
    "실적 하회", "적자 전환", "유상증자", "소송", "리콜", "상장폐지",
    "가이던스 하향", "earnings miss", "downgrade", "offering", "lawsuit", "recall",
)


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
        summary=summarize_news(stored, period=period, now=now),
        active_providers=tuple(active),
        errors=tuple(errors),
    )


def summarize_news(
    articles: list[dict], *, period: str, now: datetime | None = None
) -> NewsSummary:
    now = now or datetime.now(timezone.utc)
    cutoff = now - NEWS_WINDOWS.get(period, timedelta(days=3))
    relevant = []
    for article in articles:
        published_at = article["published_at"]
        published_utc = published_at.replace(tzinfo=timezone.utc) if published_at.tzinfo is None else published_at.astimezone(timezone.utc)
        if cutoff <= published_utc <= now:
            relevant.append((article, published_utc))
    if not relevant:
        return NewsSummary("정보 없음", 50, 0, 0, ("분석 구간에 해당하는 뉴스가 없습니다.",), None)

    weighted_total = 0.0
    total_weight = 0.0
    reasons = []
    for article, _ in relevant:
        text = f"{article.get('title', '')} {article.get('summary', '')}".lower()
        provider_score = article.get("sentiment_score")
        if provider_score is not None:
            score = max(0.0, min(100.0, (float(provider_score) + 1.0) * 50.0))
        else:
            score = 50.0
            score += 12 * sum(word.lower() in text for word in POSITIVE_WORDS)
            score -= 12 * sum(word.lower() in text for word in NEGATIVE_WORDS)
            score = max(0.0, min(100.0, score))
        relevance = article.get("relevance_score")
        weight = max(0.2, min(1.0, float(relevance))) if relevance is not None else 0.6
        if article.get("content_type") == "DISCLOSURE":
            weight = 1.0
        weighted_total += score * weight
        total_weight += weight
        if score >= 60 or score <= 40:
            reasons.append(f"{article.get('source')}: {article.get('title')}")
    score = round(weighted_total / total_weight) if total_weight else 50
    direction = "긍정" if score >= 60 else "부정" if score <= 40 else "중립"
    confidence = min(100, round(len(relevant) * 12 + total_weight * 8))
    if not reasons:
        reasons.append("강한 긍정·부정 신호 없이 중립적인 뉴스 흐름입니다.")
    latest_at = max(published_at for _, published_at in relevant)
    return NewsSummary(direction, score, confidence, len(relevant), tuple(reasons[:3]), latest_at)


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
