"""Persistence for normalized official financial statements and valuations."""

from dataclasses import asdict

from sqlalchemy import Engine, text

from .models import FundamentalResult


def save_fundamental_result(
    engine: Engine, *, symbol: str, market_country: str, result: FundamentalResult
) -> None:
    with engine.begin() as connection:
        instrument_id = connection.execute(text("""
            SELECT instrument_id FROM instruments
            WHERE symbol=:symbol AND market_country=:country
            ORDER BY instrument_id LIMIT 1
        """), {"symbol": symbol.upper(), "country": market_country.upper()}).scalar()
        if instrument_id is None:
            return
        values = asdict(result)
        values.update({"instrument_id": int(instrument_id), "source_url": result.source_url})
        connection.execute(text("""
            INSERT INTO fundamental_snapshots
              (instrument_id, provider, fiscal_year, statement_type, currency,
               revenue, operating_income, net_income, assets, liabilities, equity,
               operating_cash_flow, market_price, shares_outstanding, market_cap,
               per_ratio, pbr_ratio, psr_ratio, roe_pct, source_url)
            VALUES
              (:instrument_id, :provider, :fiscal_year, :statement_type, :currency,
               :revenue, :operating_income, :net_income, :assets, :liabilities, :equity,
               :operating_cash_flow, :market_price, :shares_outstanding, :market_cap,
               :per_ratio, :pbr_ratio, :psr_ratio, :roe_pct, :source_url)
            ON DUPLICATE KEY UPDATE
              statement_type=VALUES(statement_type), currency=VALUES(currency),
              revenue=VALUES(revenue), operating_income=VALUES(operating_income),
              net_income=VALUES(net_income), assets=VALUES(assets),
              liabilities=VALUES(liabilities), equity=VALUES(equity),
              operating_cash_flow=VALUES(operating_cash_flow),
              market_price=VALUES(market_price), shares_outstanding=VALUES(shares_outstanding),
              market_cap=VALUES(market_cap), per_ratio=VALUES(per_ratio),
              pbr_ratio=VALUES(pbr_ratio), psr_ratio=VALUES(psr_ratio), roe_pct=VALUES(roe_pct),
              source_url=VALUES(source_url), fetched_at=CURRENT_TIMESTAMP(6)
        """), values)
