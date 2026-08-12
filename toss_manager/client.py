"""Read-only Toss Securities Open API client (spec version 1.2.14)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
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
        response = self.session.post(
            f"{self.settings.api_base_url}/oauth2/token",
            data={
                "grant_type": "client_credentials",
                "client_id": self.settings.client_id,
                "client_secret": self.settings.client_secret,
            },
            timeout=self.timeout,
        )
        self._raise_for_status(response)
        payload = response.json()
        self._access_token = payload["access_token"]
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
        response = self.session.get(
            f"{self.settings.api_base_url}{path}",
            params=params,
            headers=headers,
            timeout=self.timeout,
        )
        self._raise_for_status(response)
        return response.json().get("result")

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
