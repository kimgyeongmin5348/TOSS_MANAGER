import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

from toss_manager.news.providers import AlphaVantageNewsProvider, NaverNewsProvider
from toss_manager.news.service import summarize_news


class NewsProviderTests(unittest.TestCase):
    @patch("toss_manager.news.providers.requests.get")
    def test_naver_normalizes_html_and_time(self, get) -> None:
        response = Mock()
        response.json.return_value = {"items": [{
            "title": "<b>삼성전자</b> 신규 계약",
            "description": "반도체 &amp; 공급 계약",
            "originallink": "https://example.com/1",
            "link": "https://news.naver.com/1",
            "pubDate": "Fri, 14 Aug 2026 10:00:00 +0900",
        }]}
        get.return_value = response

        articles = NaverNewsProvider("id", "secret").fetch("005930", "삼성전자")

        self.assertEqual(len(articles), 1)
        self.assertEqual(articles[0].title, "삼성전자 신규 계약")
        self.assertEqual(articles[0].summary, "반도체 & 공급 계약")
        self.assertEqual(articles[0].published_at.tzinfo, timezone.utc)
        _, kwargs = get.call_args
        self.assertEqual(
            kwargs["headers"]["X-NCP-APIGW-API-KEY-ID"], "id"
        )
        self.assertEqual(
            kwargs["headers"]["X-NCP-APIGW-API-KEY"], "secret"
        )

    @patch("toss_manager.news.providers.requests.get")
    def test_alpha_vantage_keeps_ticker_sentiment(self, get) -> None:
        response = Mock()
        response.json.return_value = {"feed": [{
            "title": "Nvidia earnings beat",
            "summary": "Strong demand",
            "source": "Example",
            "url": "https://example.com/nvda",
            "time_published": "20260814T010000",
            "ticker_sentiment": [{
                "ticker": "NVDA",
                "ticker_sentiment_score": "0.6",
                "relevance_score": "0.9",
            }],
        }]}
        get.return_value = response

        article = AlphaVantageNewsProvider("key").fetch("NVDA", "Nvidia")[0]

        self.assertEqual(article.sentiment_score, 0.6)
        self.assertEqual(article.relevance_score, 0.9)


class NewsSummaryTests(unittest.TestCase):
    def test_period_window_excludes_old_news(self) -> None:
        now = datetime(2026, 8, 14, 10, tzinfo=timezone.utc)
        articles = [
            {
                "title": "신규 계약 체결",
                "summary": "대규모 수주",
                "source": "뉴스",
                "content_type": "NEWS",
                "published_at": now - timedelta(minutes=10),
                "sentiment_score": None,
                "relevance_score": None,
            },
            {
                "title": "오래된 실적 상회",
                "summary": "",
                "source": "뉴스",
                "content_type": "NEWS",
                "published_at": now - timedelta(hours=3),
                "sentiment_score": None,
                "relevance_score": None,
            },
        ]

        result = summarize_news(articles, period="1분", now=now)

        self.assertEqual(result.article_count, 1)
        self.assertEqual(result.direction, "긍정")
        self.assertGreater(result.score, 50)

    def test_no_current_news_returns_unknown(self) -> None:
        result = summarize_news([], period="5분")
        self.assertEqual(result.direction, "정보 없음")
        self.assertEqual(result.confidence, 0)

    def test_unrelated_mentions_are_excluded_and_confidence_is_composite(self) -> None:
        now = datetime(2026, 8, 14, 10, tzinfo=timezone.utc)
        articles = [
            {
                "title": "SK하이닉스 신규 계약",
                "summary": "SK하이닉스가 공급 계약을 체결했다.",
                "source": "뉴스",
                "content_type": "NEWS",
                "published_at": now - timedelta(minutes=5),
                "sentiment_score": None,
                "relevance_score": None,
            },
            {
                "title": "다른 반도체 회사 소식",
                "summary": "경쟁사 실적 기사",
                "source": "뉴스",
                "content_type": "NEWS",
                "published_at": now - timedelta(minutes=5),
                "sentiment_score": None,
                "relevance_score": None,
            },
        ]

        result = summarize_news(
            articles,
            period="1분",
            now=now,
            symbol="000660",
            name="SK하이닉스",
        )

        self.assertEqual(result.article_count, 1)
        self.assertEqual(result.excluded_count, 1)
        self.assertEqual(result.positive_count, 1)
        self.assertLess(result.confidence, 100)


if __name__ == "__main__":
    unittest.main()
