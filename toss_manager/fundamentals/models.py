from dataclasses import dataclass


@dataclass(frozen=True)
class FundamentalResult:
    provider: str
    fiscal_year: int
    currency: str
    statement_type: str
    revenue: float | None
    operating_income: float | None
    net_income: float | None
    assets: float | None
    liabilities: float | None
    equity: float | None
    operating_cash_flow: float | None
    market_price: float | None
    shares_outstanding: float | None
    market_cap: float | None
    per_ratio: float | None
    pbr_ratio: float | None
    psr_ratio: float | None
    roe_pct: float | None
    source_url: str
    limitations: tuple[str, ...]
