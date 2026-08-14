"""OpenDART and SEC EDGAR official financial-statement clients."""

from __future__ import annotations

from datetime import datetime
from io import BytesIO
from xml.etree import ElementTree
from zipfile import ZipFile

import requests


class FundamentalsError(RuntimeError):
    pass


class OpenDartFinancialProvider:
    def __init__(self, api_key: str, *, timeout: float = 15) -> None:
        self.api_key = api_key
        self.timeout = timeout

    def _corp_code(self, symbol: str) -> str:
        response = requests.get(
            "https://opendart.fss.or.kr/api/corpCode.xml",
            params={"crtfc_key": self.api_key}, timeout=self.timeout,
        )
        response.raise_for_status()
        with ZipFile(BytesIO(response.content)) as archive:
            root = ElementTree.fromstring(archive.read(archive.namelist()[0]))
        code = symbol.zfill(6)
        for item in root.findall("list"):
            if item.findtext("stock_code", "").strip() == code:
                return item.findtext("corp_code", "").strip()
        raise FundamentalsError("OpenDART에서 종목 고유번호를 찾지 못했습니다.")

    def fetch(self, symbol: str) -> tuple[int, str, list[dict]]:
        try:
            corp_code = self._corp_code(symbol)
            for year in range(datetime.now().year - 1, datetime.now().year - 5, -1):
                for fs_div in ("CFS", "OFS"):
                    response = requests.get(
                        "https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json",
                        params={"crtfc_key": self.api_key, "corp_code": corp_code,
                                "bsns_year": year, "reprt_code": "11011", "fs_div": fs_div},
                        timeout=self.timeout,
                    )
                    response.raise_for_status()
                    payload = response.json()
                    if payload.get("status") == "000" and payload.get("list"):
                        return year, fs_div, payload["list"]
            raise FundamentalsError("최근 사업보고서 재무제표가 없습니다.")
        except FundamentalsError:
            raise
        except (requests.RequestException, ValueError, OSError) as exc:
            raise FundamentalsError(f"OpenDART 재무제표 조회 실패: {exc}") from exc


class SecFinancialProvider:
    def __init__(self, user_agent: str, *, timeout: float = 15) -> None:
        self.headers = {"User-Agent": user_agent, "Accept-Encoding": "gzip, deflate"}
        self.timeout = timeout

    def fetch(self, symbol: str) -> tuple[int, str, dict]:
        if not self.headers["User-Agent"]:
            raise FundamentalsError("SEC_USER_AGENT에 앱 이름과 연락처를 설정해 주세요.")
        try:
            tickers = requests.get(
                "https://www.sec.gov/files/company_tickers.json",
                headers=self.headers, timeout=self.timeout,
            )
            tickers.raise_for_status()
            match = next(
                (item for item in tickers.json().values()
                 if str(item.get("ticker", "")).upper() == symbol.upper()), None
            )
            if not match:
                raise FundamentalsError("SEC에서 티커의 CIK를 찾지 못했습니다.")
            cik = str(match["cik_str"]).zfill(10)
            response = requests.get(
                f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json",
                headers=self.headers, timeout=self.timeout,
            )
            response.raise_for_status()
            facts = response.json().get("facts", {}).get("us-gaap", {})
            years = [
                int(item["fy"]) for concept in facts.values()
                for units in concept.get("units", {}).values() for item in units
                if item.get("form") == "10-K" and item.get("fp") == "FY" and item.get("fy")
            ]
            if not years:
                raise FundamentalsError("SEC에서 최신 연간 재무제표를 찾지 못했습니다.")
            return max(years), cik, facts
        except FundamentalsError:
            raise
        except (requests.RequestException, ValueError, OSError) as exc:
            raise FundamentalsError(f"SEC 재무제표 조회 실패: {exc}") from exc
