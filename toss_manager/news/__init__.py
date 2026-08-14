"""Optional market-news collection and sentiment summaries."""

from .models import NewsArticle, NewsSummary
from .service import sync_symbol_news

__all__ = ["NewsArticle", "NewsSummary", "sync_symbol_news"]
