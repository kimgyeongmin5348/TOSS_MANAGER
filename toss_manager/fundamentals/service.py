"""Normalize official filings and calculate current-price valuation ratios."""

from __future__ import annotations

from typing import Any

from toss_manager.config import FundamentalsSettings

from .models import FundamentalResult
from .providers import FundamentalsError, OpenDartFinancialProvider, SecFinancialProvider


KR_TAGS = {
    "revenue": ("ifrs-full_Revenue", "ifrs-full_RevenueFromContractsWithCustomers"),
    "operating_income": ("dart_OperatingIncomeLoss", "ifrs-full_ProfitLossFromOperatingActivities"),
    "net_income": ("ifrs-full_ProfitLoss",), "assets": ("ifrs-full_Assets",),
    "liabilities": ("ifrs-full_Liabilities",), "equity": ("ifrs-full_Equity",),
    "operating_cash_flow": ("ifrs-full_CashFlowsFromUsedInOperatingActivities",),
}
US_TAGS = {
    "revenue": ("RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues", "SalesRevenueNet"),
    "operating_income": ("OperatingIncomeLoss",), "net_income": ("NetIncomeLoss",),
    "assets": ("Assets",), "liabilities": ("Liabilities",),
    "equity": ("StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"),
    "operating_cash_flow": ("NetCashProvidedByUsedInOperatingActivities",),
}


def _number(value: Any) -> float | None:
    try:
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None


def _ratio(numerator: float | None, denominator: float | None) -> float | None:
    return numerator / denominator if numerator is not None and denominator is not None and denominator > 0 else None


def _kr_values(rows: list[dict]) -> dict[str, float | None]:
    statement_by_key = {
        "revenue": ("IS", "CIS"), "operating_income": ("IS", "CIS"),
        "net_income": ("IS", "CIS"), "assets": ("BS",),
        "liabilities": ("BS",), "equity": ("BS",),
        "operating_cash_flow": ("CF",),
    }
    values = {}
    for key, tags in KR_TAGS.items():
        values[key] = next((
            _number(row.get("thstrm_amount"))
            for division in statement_by_key[key]
            for tag in tags
            for row in rows
            if row.get("sj_div") == division and row.get("account_id") == tag
            and _number(row.get("thstrm_amount")) is not None
        ), None)
    return values


def _sec_fact(facts: dict, tags: tuple[str, ...], year: int, unit: str = "USD") -> float | None:
    candidates = []
    for tag in tags:
        for item in facts.get(tag, {}).get("units", {}).get(unit, []):
            if item.get("form") == "10-K" and item.get("fp") == "FY" and int(item.get("fy", 0)) == year:
                candidates.append(item)
    if not candidates:
        return None
    latest = max(candidates, key=lambda item: (str(item.get("filed", "")), str(item.get("end", ""))))
    return _number(latest.get("val"))


def load_company_fundamentals(
    *, symbol: str, market_country: str, market_price: float | None,
    shares_outstanding: float | None, settings: FundamentalsSettings | None = None,
) -> FundamentalResult:
    settings = settings or FundamentalsSettings.from_env()
    if market_country.upper() == "KR":
        if not settings.opendart_api_key:
            raise FundamentalsError("OPENDART_API_KEY가 설정되지 않았습니다.")
        year, statement, rows = OpenDartFinancialProvider(settings.opendart_api_key).fetch(symbol)
        values = _kr_values(rows)
        provider, currency = "OPENDART", "KRW"
        source = "https://dart.fss.or.kr/"
    else:
        year, cik, facts = SecFinancialProvider(settings.sec_user_agent).fetch(symbol)
        values = {key: _sec_fact(facts, tags, year) for key, tags in US_TAGS.items()}
        statement, provider, currency = "CONSOLIDATED", "SEC_EDGAR", "USD"
        source = f"https://www.sec.gov/edgar/browse/?CIK={cik}"
    price = _number(market_price)
    shares = _number(shares_outstanding)
    market_cap = price * shares if price and shares and price > 0 and shares > 0 else None
    net_income, equity, revenue = values["net_income"], values["equity"], values["revenue"]
    return FundamentalResult(
        provider=provider, fiscal_year=year, currency=currency, statement_type=statement,
        market_price=price, shares_outstanding=shares, market_cap=market_cap,
        per_ratio=_ratio(market_cap, net_income), pbr_ratio=_ratio(market_cap, equity),
        psr_ratio=_ratio(market_cap, revenue),
        roe_pct=(net_income / equity * 100) if net_income is not None and equity and equity > 0 else None,
        source_url=source,
        limitations=("최신 연간 공시 기준이며 최근 12개월·시장 예상치와 다를 수 있습니다.",
                     "공시 정정과 현재가 변동에 따라 지표가 달라질 수 있습니다."),
        **values,
    )
