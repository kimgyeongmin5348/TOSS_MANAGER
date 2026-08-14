"""Provider-neutral news data models."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class NewsArticle:
    provider: str
    external_id: str
    title: str
    summary: str
    source: str
    url: str
    published_at: datetime
    content_type: str = "NEWS"
    sentiment_score: float | None = None
    relevance_score: float | None = None


@dataclass(frozen=True)
class NewsSummary:
    direction: str
    score: int
    confidence: int
    article_count: int
    reasons: tuple[str, ...]
    latest_at: datetime | None
    positive_count: int
    neutral_count: int
    negative_count: int
    excluded_count: int
    average_relevance: int
    agreement: int
    methodology: tuple[str, ...]


@dataclass(frozen=True)
class NewsSyncResult:
    summary: NewsSummary
    active_providers: tuple[str, ...]
    errors: tuple[str, ...]
