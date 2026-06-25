"""Real market data → a backtest Universe (guarded; falls back to synthetic).

Two sources, both optional and behind clean guards so the system never stalls:

- **Fundamentals**: the ``edgartools`` library (the edgartools-mcp engine) gives
  XBRL facts per ticker as of a filing date. We derive the value factors NYX
  cares about: margin of safety, ROIC, debt/equity, owner-earnings yield.
- **Forward returns**: a ``PriceSource`` (default: Stooq CSV) gives the price at
  T and ~1y later, so we can compute the realized return the analyst is scored on.

If ``edgartools`` isn't installed, the network is blocked, or a fetch fails, the
loader raises a clear ``DataUnavailable`` and callers fall back to the synthetic
universe. The factor math is pure and unit-tested with injected fakes, so the
logic is verified even where live data can't be reached.
"""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass

from .backtest import Company, Universe


class DataUnavailable(RuntimeError):
    """Raised when live data can't be fetched (missing lib / blocked / error)."""


@dataclass
class RawFundamentals:
    """The minimal inputs we need per company, however they're sourced."""
    ticker: str
    price: float
    intrinsic_value: float
    roic: float
    debt_to_equity: float
    owner_earnings_yield: float


def fundamentals_to_company(f: RawFundamentals, forward_return: float) -> Company:
    return Company(
        ticker=f.ticker, price=round(f.price, 2), intrinsic_value=round(f.intrinsic_value, 2),
        roic=round(f.roic, 4), debt_to_equity=round(f.debt_to_equity, 3),
        owner_earnings_yield=round(f.owner_earnings_yield, 4),
        forward_return=round(forward_return, 4),
    )


# -- fundamentals from EDGAR (optional) -------------------------------------
def edgar_fundamentals(ticker: str, *, identity: str = "") -> RawFundamentals:  # pragma: no cover
    """Derive value factors from edgartools. Needs the lib + network + identity."""
    try:
        import edgar  # type: ignore
    except ImportError as exc:
        raise DataUnavailable("edgartools not installed (pip install 'edgartools[ai]')") from exc
    import os

    ident = identity or os.environ.get("EDGAR_IDENTITY", "")
    if not ident:
        raise DataUnavailable("EDGAR_IDENTITY not set")
    try:
        edgar.set_identity(ident)
        company = edgar.Company(ticker)
        fin = company.get_financials()
        bs, is_, cf = fin.balance_sheet(), fin.income_statement(), fin.cash_flow_statement()

        def g(stmt, *keys):  # tolerant lookup across label variants
            for k in keys:
                try:
                    val = stmt.loc[k].iloc[0]
                    if val is not None:
                        return float(val)
                except Exception:  # noqa: BLE001
                    continue
            return 0.0

        net_income = g(is_, "NetIncome", "Net Income")
        total_debt = g(bs, "TotalDebt", "Long Term Debt", "LongTermDebt")
        equity = g(bs, "StockholdersEquity", "Total Equity") or 1.0
        assets = g(bs, "TotalAssets", "Total Assets") or 1.0
        op_cf = g(cf, "OperatingCashFlow", "Net Cash Provided by Operating Activities")
        capex = abs(g(cf, "CapitalExpenditure", "Purchases of Property and Equipment"))
        mcap = float(getattr(company, "market_cap", 0.0) or 0.0)

        owner_earnings = op_cf - capex
        invested_capital = equity + total_debt or 1.0
        return RawFundamentals(
            ticker=ticker.upper(),
            price=mcap or assets,                       # placeholder if no live price
            intrinsic_value=max(owner_earnings, 0.0) * 12.0,   # crude 12x owner-earnings
            roic=net_income / invested_capital,
            debt_to_equity=total_debt / equity,
            owner_earnings_yield=(owner_earnings / mcap) if mcap else 0.0,
        )
    except DataUnavailable:
        raise
    except Exception as exc:  # noqa: BLE001
        raise DataUnavailable(f"EDGAR fetch failed for {ticker}: {exc}") from exc


# -- forward returns from a price source ------------------------------------
def stooq_forward_return(fetcher, ticker: str, *, as_of: str, horizon_days: int = 252) -> float:  # pragma: no cover
    """Realized forward return from Stooq daily CSV via the (allowlisted) fetcher."""
    url = f"https://stooq.com/q/d/l/?s={ticker.lower()}.us&i=d"
    try:
        doc = fetcher.fetch(url)
        rows = list(csv.DictReader(io.StringIO(doc.text)))
        dated = [(r["Date"], float(r["Close"])) for r in rows if r.get("Close")]
        start = next((p for d, p in dated if d >= as_of), None)
        idx = next((i for i, (d, _) in enumerate(dated) if d >= as_of), None)
        if start is None or idx is None or idx + horizon_days >= len(dated):
            raise DataUnavailable(f"insufficient price history for {ticker}")
        end = dated[idx + horizon_days][1]
        return (end - start) / start
    except DataUnavailable:
        raise
    except Exception as exc:  # noqa: BLE001
        raise DataUnavailable(f"price fetch failed for {ticker}: {exc}") from exc


# -- assemble a universe -----------------------------------------------------
def build_universe(
    tickers: list[str],
    *,
    as_of: str = "2020-01-02",
    fundamentals_fn=None,
    forward_return_fn=None,
    identity: str = "",
    fetcher=None,
) -> Universe:
    """Build a real Universe. Injectable fns make the logic unit-testable; the
    live defaults use EDGAR + Stooq. Raises DataUnavailable if nothing loads."""
    fundamentals_fn = fundamentals_fn or (lambda t: edgar_fundamentals(t, identity=identity))
    forward_return_fn = forward_return_fn or (
        lambda t: stooq_forward_return(fetcher, t, as_of=as_of))

    companies: list[Company] = []
    errors = 0
    for t in tickers:
        try:
            f = fundamentals_fn(t)
            ret = forward_return_fn(t)
            companies.append(fundamentals_to_company(f, ret))
        except DataUnavailable:
            errors += 1
            continue
    if not companies:
        raise DataUnavailable(f"no companies loaded ({errors} failures)")
    return Universe(as_of=as_of, companies=companies)


def try_build_universe(tickers, **kwargs) -> Universe | None:
    """Best-effort: return a real Universe or None (caller uses synthetic)."""
    try:
        return build_universe(tickers, **kwargs)
    except DataUnavailable:
        return None
