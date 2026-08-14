"""Read-only Toss Securities Open API client (spec version 1.2.14)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import time
from typing import Any, Iterable

import requests

from .config import Settings


class TossAPIError(RuntimeError):
    """API failure with status and request ID preserved for troubleshooting."""


class TossAPIClient:
    def __init__(self, settings: Settings, *, timeout: float = 15.0) -> None:
        self.settings = settings
        self.timeout = timeout
        self.session = requests.Session()
        self._access_token: str | None = None
        self._expires_at = datetime.min.replace(tzinfo=timezone.utc)

    def _token(self) -> str:
        # Keep a 60-second margin. Reissuing invalidates the previous token, so cache it.
        if self._access_token and datetime.now(timezone.utc) < self._expires_at:
            return self._access_token
        try:
            response = self.session.post(
                f"{self.settings.api_base_url}/oauth2/token",
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.settings.client_id,
                    "client_secret": self.settings.client_secret,
                },
                timeout=self.timeout,
            )
        except requests.Timeout as exc:
            raise TossAPIError("토스 API 인증 요청 시간이 초과되었습니다.") from exc
        except requests.RequestException as exc:
            raise TossAPIError("토스 API 인증 서버에 연결하지 못했습니다.") from exc
        self._raise_for_status(response)
        payload = self._json(response)
        try:
            self._access_token = payload["access_token"]
        except (KeyError, TypeError) as exc:
            raise TossAPIError("토스 API 인증 응답 형식이 올바르지 않습니다.") from exc
        lifetime = max(int(payload.get("expires_in", 3600)) - 60, 1)
        self._expires_at = datetime.now(timezone.utc) + timedelta(seconds=lifetime)
        return self._access_token

    def _get(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        account_seq: int | None = None,
    ) -> Any:
        headers = {"Authorization": f"Bearer {self._token()}"}
        if account_seq is not None:
            headers["X-Tossinvest-Account"] = str(account_seq)
        try:
            response = self.session.get(
                f"{self.settings.api_base_url}{path}",
                params=params,
                headers=headers,
                timeout=self.timeout,
            )
        except requests.Timeout as exc:
            raise TossAPIError("토스 API 조회 요청 시간이 초과되었습니다.") from exc
        except requests.RequestException as exc:
            raise TossAPIError("토스 API 서버에 연결하지 못했습니다.") from exc
        self._raise_for_status(response)
        payload = self._json(response)
        if not isinstance(payload, dict):
            raise TossAPIError("토스 API 응답 형식이 올바르지 않습니다.")
        return payload.get("result")

    @staticmethod
    def _json(response: requests.Response) -> Any:
        try:
            return response.json()
        except ValueError as exc:
            raise TossAPIError("토스 API가 올바른 JSON을 반환하지 않았습니다.") from exc

    @staticmethod
    def _raise_for_status(response: requests.Response) -> None:
        if response.ok:
            return
        request_id = response.headers.get("X-Request-Id", "unknown")
        try:
            detail = response.json()
        except ValueError:
            detail = response.text[:500]
        raise TossAPIError(
            f"Toss API {response.status_code} (request_id={request_id}): {detail}"
        )

    @staticmethod
    def _symbols(symbols: Iterable[str]) -> str:
        values = [str(symbol).strip().upper() for symbol in symbols if str(symbol).strip()]
        if not 1 <= len(values) <= 200:
            raise ValueError("symbols는 1~200개여야 합니다.")
        return ",".join(values)

    def get_accounts(self) -> list[dict[str, Any]]:
        return self._get("/api/v1/accounts")

    def get_holdings(self, account_seq: int, symbol: str | None = None) -> dict[str, Any]:
        params = {"symbol": symbol.upper()} if symbol else None
        return self._get("/api/v1/holdings", params=params, account_seq=account_seq)

    def get_prices(self, symbols: Iterable[str]) -> list[dict[str, Any]]:
        return self._get("/api/v1/prices", params={"symbols": self._symbols(symbols)})

    def get_stocks(self, symbols: Iterable[str]) -> list[dict[str, Any]]:
        return self._get("/api/v1/stocks", params={"symbols": self._symbols(symbols)})

    def get_rankings(
        self, market_country: str = "US", *, count: int = 50
    ) -> dict[str, Any]:
        """Return the market-wide realtime trading-volume ranking."""
        if market_country not in {"US", "KR"}:
            raise ValueError("market_country must be US or KR")
        if not 1 <= count <= 100:
            raise ValueError("count must be between 1 and 100")
        return self._get(
            "/api/v1/rankings",
            params={
                "type": "MARKET_TRADING_VOLUME",
                "marketCountry": market_country,
                "duration": "realtime",
                "excludeInvestmentCaution": "false",
                "count": count,
            },
        )

    def get_candles(
        self,
        symbol: str,
        *,
        interval: str = "1d",
        count: int = 100,
        before: str | None = None,
        adjusted: bool = True,
    ) -> dict[str, Any]:
        if interval not in {"1m", "1d"}:
            raise ValueError("interval은 '1m' 또는 '1d'만 가능합니다.")
        if not 1 <= count <= 200:
            raise ValueError("count는 1~200이어야 합니다.")
        params: dict[str, Any] = {
            "symbol": symbol.upper(), "interval": interval,
            "count": count, "adjusted": str(adjusted).lower(),
        }
        if before:
            params["before"] = before
        return self._get("/api/v1/candles", params=params)

    def get_candle_history(
        self,
        symbol: str,
        *,
        years: int = 5,
        interval: str = "1d",
        adjusted: bool = True,
        max_pages: int = 12,
    ) -> dict[str, Any]:
        """Page backward through official candles and return a deduplicated history."""
        if interval != "1d":
            raise ValueError("장기 이력 수집은 일봉만 지원합니다.")
        if not 1 <= years <= 10:
            raise ValueError("수집 기간은 1~10년이어야 합니다.")
        cutoff = datetime.now(timezone.utc) - timedelta(days=round(years * 365.25))
        before: str | None = None
        candles_by_timestamp: dict[str, dict[str, Any]] = {}

        for page_number in range(max_pages):
            payload = self.get_candles(
                symbol, interval=interval, count=200, before=before, adjusted=adjusted
            )
            page = payload.get("candles", []) if payload else []
            if not page:
                break
            for candle in page:
                timestamp = str(candle.get("timestamp", ""))
                if timestamp:
                    candles_by_timestamp[timestamp] = candle

            oldest = min(
                datetime.fromisoformat(str(candle["timestamp"]).replace("Z", "+00:00"))
                for candle in page
            )
            if oldest.astimezone(timezone.utc) <= cutoff:
                break
            next_before = payload.get("nextBefore")
            if not next_before or next_before == before:
                break
            before = next_before
            if page_number + 1 < max_pages:
                time.sleep(0.22)

        filtered = [
            candle for candle in candles_by_timestamp.values()
            if datetime.fromisoformat(str(candle["timestamp"]).replace("Z", "+00:00")).astimezone(timezone.utc) >= cutoff
        ]
        filtered.sort(key=lambda candle: str(candle["timestamp"]))
        return {"candles": filtered, "years": years}

    def get_candle_window(
        self,
        symbol: str,
        *,
        interval: str = "1m",
        target_count: int = 200,
        adjusted: bool = True,
        max_pages: int = 20,
    ) -> dict[str, Any]:
        """Page backward until a recent, deduplicated candle window is filled."""
        if interval not in {"1m", "1d"}:
            raise ValueError("interval은 '1m' 또는 '1d'만 가능합니다.")
        if not 1 <= target_count <= max_pages * 200:
            raise ValueError("target_count가 페이지 수집 한도를 벗어났습니다.")

        before: str | None = None
        candles_by_timestamp: dict[str, dict[str, Any]] = {}
        for page_number in range(max_pages):
            payload = self.get_candles(
                symbol, interval=interval, count=200,
                before=before, adjusted=adjusted,
            )
            page = payload.get("candles", []) if payload else []
            if not page:
                break
            for candle in page:
                timestamp = str(candle.get("timestamp", ""))
                if timestamp:
                    candles_by_timestamp[timestamp] = candle
            if len(candles_by_timestamp) >= target_count:
                break
            next_before = payload.get("nextBefore")
            if not next_before or next_before == before:
                break
            before = next_before
            if page_number + 1 < max_pages:
                time.sleep(0.22)

        candles = sorted(
            candles_by_timestamp.values(), key=lambda item: str(item["timestamp"])
        )
        return {
            "candles": candles[-target_count:],
            "requestedCount": target_count,
        }

    def get_candles_since(
        self,
        symbol: str,
        *,
        since: datetime,
        interval: str = "1d",
        adjusted: bool = True,
        max_pages: int = 20,
    ) -> dict[str, Any]:
        """Fetch newest pages backward until they overlap the last stored candle."""
        if interval != "1d":
            raise ValueError("증분 이력 수집은 일봉만 지원합니다.")
        boundary = since.replace(tzinfo=timezone.utc) if since.tzinfo is None else since.astimezone(timezone.utc)
        before: str | None = None
        candles_by_timestamp: dict[str, dict[str, Any]] = {}
        for page_number in range(max_pages):
            payload = self.get_candles(
                symbol, interval=interval, count=200, before=before, adjusted=adjusted
            )
            page = payload.get("candles", []) if payload else []
            if not page:
                break
            parsed = [
                datetime.fromisoformat(str(candle["timestamp"]).replace("Z", "+00:00")).astimezone(timezone.utc)
                for candle in page
            ]
            for candle, timestamp in zip(page, parsed):
                if timestamp >= boundary:
                    candles_by_timestamp[str(candle["timestamp"])] = candle
            if min(parsed) <= boundary:
                break
            next_before = payload.get("nextBefore")
            if not next_before or next_before == before:
                break
            before = next_before
            if page_number + 1 < max_pages:
                time.sleep(0.22)
        candles = sorted(candles_by_timestamp.values(), key=lambda item: str(item["timestamp"]))
        return {"candles": candles, "since": boundary.isoformat()}
