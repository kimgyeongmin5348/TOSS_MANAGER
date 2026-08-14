"""TiDB persistence for provider-neutral news articles."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Engine, text

from .models import NewsArticle


def latest_collection_at(
    engine: Engine, *, symbol: str, market_country: str, provider: str
) -> datetime | None:
    with engine.connect() as connection:
        return connection.execute(text("""
            SELECT s.last_success_at
            FROM news_collection_state s
            JOIN instruments i ON i.instrument_id=s.instrument_id
            WHERE i.symbol=:symbol AND i.market_country=:country
              AND s.provider=:provider
        """), {
            "symbol": symbol.upper(),
            "country": market_country.upper(),
            "provider": provider,
        }).scalar()


def mark_collection_success(
    engine: Engine, *, symbol: str, market_country: str, provider: str
) -> None:
    with engine.begin() as connection:
        connection.execute(text("""
            INSERT INTO news_collection_state (instrument_id, provider, last_success_at)
            SELECT instrument_id, :provider, UTC_TIMESTAMP(6)
            FROM instruments
            WHERE symbol=:symbol AND market_country=:country
            ORDER BY instrument_id LIMIT 1
            ON DUPLICATE KEY UPDATE
              last_success_at=VALUES(last_success_at),
              updated_at=CURRENT_TIMESTAMP(6)
        """), {
            "symbol": symbol.upper(),
            "country": market_country.upper(),
            "provider": provider,
        })


def upsert_news_articles(
    engine: Engine,
    *,
    symbol: str,
    market_country: str,
    articles: list[NewsArticle],
) -> None:
    if not articles:
        return
    with engine.begin() as connection:
        instrument_id = connection.execute(text("""
            SELECT instrument_id FROM instruments
            WHERE symbol=:symbol AND market_country=:country
            ORDER BY instrument_id LIMIT 1
        """), {
            "symbol": symbol.upper(), "country": market_country.upper(),
        }).scalar_one()
        records = []
        collected_at = datetime.now(timezone.utc).replace(tzinfo=None)
        for article in articles:
            published_at = article.published_at
            if published_at.tzinfo is not None:
                published_at = published_at.astimezone(timezone.utc).replace(tzinfo=None)
            records.append({
                "instrument_id": int(instrument_id),
                "provider": article.provider,
                "external_id": article.external_id,
                "content_type": article.content_type,
                "title": article.title,
                "summary": article.summary,
                "source": article.source,
                "article_url": article.url,
                "published_at": published_at,
                "collected_at": collected_at,
                "sentiment_score": article.sentiment_score,
                "relevance_score": article.relevance_score,
            })
        connection.execute(text("""
            INSERT INTO news_articles
              (instrument_id, provider, external_id, content_type, title,
               summary, source, article_url, published_at, collected_at,
               sentiment_score, relevance_score)
            VALUES
              (:instrument_id, :provider, :external_id, :content_type, :title,
               :summary, :source, :article_url, :published_at, :collected_at,
               :sentiment_score, :relevance_score)
            ON DUPLICATE KEY UPDATE
              title=VALUES(title), summary=VALUES(summary), source=VALUES(source),
              article_url=VALUES(article_url), published_at=VALUES(published_at),
              collected_at=VALUES(collected_at),
              sentiment_score=VALUES(sentiment_score),
              relevance_score=VALUES(relevance_score),
              updated_at=CURRENT_TIMESTAMP(6)
        """), records)


def load_recent_news(
    engine: Engine,
    *,
    symbol: str,
    market_country: str,
    limit: int = 200,
) -> list[dict[str, Any]]:
    with engine.connect() as connection:
        return list(connection.execute(text("""
            SELECT n.provider, n.external_id, n.content_type, n.title,
                   n.summary, n.source, n.article_url, n.published_at,
                   n.sentiment_score, n.relevance_score
            FROM news_articles n
            JOIN instruments i ON i.instrument_id=n.instrument_id
            WHERE i.symbol=:symbol AND i.market_country=:country
              AND n.published_at >= UTC_TIMESTAMP(6) - INTERVAL 60 DAY
            ORDER BY n.published_at DESC
            LIMIT :limit
        """), {
            "symbol": symbol.upper(),
            "country": market_country.upper(),
            "limit": int(limit),
        }).mappings())
