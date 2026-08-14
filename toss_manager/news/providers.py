"""Official API clients for Naver News, OpenDART, and Alpha Vantage."""

from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from hashlib import sha256
from html import unescape
from io import BytesIO
import re
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile

import requests

from .models import NewsArticle


class NewsProviderError(RuntimeError):
    pass


def _clean_html(value: str | None) -> str:
    return unescape(re.sub(r"<[^>]+>", "", value or "")).strip()


def _external_id(provider: str, value: str) -> str:
    return sha256(f"{provider}:{value}".encode("utf-8")).hexdigest()


class NaverNewsProvider:
    url = "https://naverapihub.apigw.ntruss.com/search/v1/news"

    def __init__(self, client_id: str, client_secret: str, *, timeout: float = 10):
        self.headers = {
            "X-NCP-APIGW-API-KEY-ID": client_id,
            "X-NCP-APIGW-API-KEY": client_secret,
        }
        self.timeout = timeout

    def fetch(self, symbol: str, name: str) -> list[NewsArticle]:
        try:
            response = requests.get(
                self.url,
                headers=self.headers,
                params={"query": f"{name} {symbol}", "display": 100, "sort": "date"},
                timeout=self.timeout,
            )
            response.raise_for_status()
            items = response.json().get("items", [])
        except (requests.RequestException, ValueError) as exc:
            raise NewsProviderError(f"네이버 뉴스 조회 실패: {exc}") from exc

        articles = []
        for item in items:
            url = item.get("originallink") or item.get("link") or ""
            if not url or not item.get("pubDate"):
                continue
            articles.append(NewsArticle(
                provider="NAVER",
                external_id=_external_id("NAVER", url),
                title=_clean_html(item.get("title")),
                summary=_clean_html(item.get("description")),
                source="네이버 뉴스",
                url=url,
                published_at=parsedate_to_datetime(item["pubDate"]).astimezone(timezone.utc),
            ))
        return articles


class OpenDartProvider:
    corp_code_url = "https://opendart.fss.or.kr/api/corpCode.xml"
    disclosure_url = "https://opendart.fss.or.kr/api/list.json"

    def __init__(self, api_key: str, *, timeout: float = 15):
        self.api_key = api_key
        self.timeout = timeout
        self._corp_codes: dict[str, str] | None = None

    def _load_corp_codes(self) -> dict[str, str]:
        if self._corp_codes is not None:
            return self._corp_codes
        try:
            response = requests.get(
                self.corp_code_url,
                params={"crtfc_key": self.api_key},
                timeout=self.timeout,
            )
            response.raise_for_status()
            with ZipFile(BytesIO(response.content)) as archive:
                xml_name = archive.namelist()[0]
                root = ElementTree.fromstring(archive.read(xml_name))
        except (
            requests.RequestException,
            ValueError,
            OSError,
            BadZipFile,
            ElementTree.ParseError,
        ) as exc:
            raise NewsProviderError(f"OpenDART 종목 코드 조회 실패: {exc}") from exc
        self._corp_codes = {
            item.findtext("stock_code", "").strip(): item.findtext("corp_code", "").strip()
            for item in root.findall("list")
            if item.findtext("stock_code", "").strip()
        }
        return self._corp_codes

    def fetch(self, symbol: str, name: str) -> list[NewsArticle]:
        corp_code = self._load_corp_codes().get(symbol.zfill(6))
        if not corp_code:
            return []
        try:
            response = requests.get(
                self.disclosure_url,
                params={
                    "crtfc_key": self.api_key,
                    "corp_code": corp_code,
                    "sort": "date",
                    "sort_mth": "desc",
                    "page_count": 100,
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise NewsProviderError(f"OpenDART 공시 조회 실패: {exc}") from exc
        if payload.get("status") not in {"000", "013"}:
            raise NewsProviderError(f"OpenDART 응답 오류: {payload.get('message', 'unknown')}")

        articles = []
        for item in payload.get("list", []):
            receipt = str(item.get("rcept_no", ""))
            date = str(item.get("rcept_dt", ""))
            if not receipt or len(date) != 8:
                continue
            articles.append(NewsArticle(
                provider="OPENDART",
                external_id=receipt,
                title=_clean_html(item.get("report_nm")),
                summary=f"{name} 공식 공시",
                source="금융감독원 전자공시",
                url=f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={receipt}",
                published_at=datetime.strptime(date, "%Y%m%d").replace(tzinfo=timezone.utc),
                content_type="DISCLOSURE",
                relevance_score=1.0,
            ))
        return articles


class AlphaVantageNewsProvider:
    url = "https://www.alphavantage.co/query"

    def __init__(self, api_key: str, *, timeout: float = 15):
        self.api_key = api_key
        self.timeout = timeout

    def fetch(self, symbol: str, name: str) -> list[NewsArticle]:
        try:
            response = requests.get(
                self.url,
                params={
                    "function": "NEWS_SENTIMENT",
                    "tickers": symbol,
                    "sort": "LATEST",
                    "limit": 100,
                    "apikey": self.api_key,
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise NewsProviderError(f"Alpha Vantage 뉴스 조회 실패: {exc}") from exc
        if "feed" not in payload:
            message = payload.get("Information") or payload.get("Note") or "잘못된 응답"
            raise NewsProviderError(f"Alpha Vantage 응답 오류: {message}")

        articles = []
        for item in payload["feed"]:
            ticker = next((value for value in item.get("ticker_sentiment", [])
                           if value.get("ticker", "").upper() == symbol.upper()), {})
            url = item.get("url", "")
            if not url or not item.get("time_published"):
                continue
            try:
                published_at = datetime.strptime(
                    item["time_published"], "%Y%m%dT%H%M%S"
                ).replace(tzinfo=timezone.utc)
            except ValueError:
                continue
            articles.append(NewsArticle(
                provider="ALPHA_VANTAGE",
                external_id=_external_id("ALPHA_VANTAGE", url),
                title=_clean_html(item.get("title")),
                summary=_clean_html(item.get("summary")),
                source=item.get("source") or "Alpha Vantage",
                url=url,
                published_at=published_at,
                sentiment_score=_float_or_none(ticker.get("ticker_sentiment_score")),
                relevance_score=_float_or_none(ticker.get("relevance_score")),
            ))
        return articles


def _float_or_none(value: object) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None
