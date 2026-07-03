"""Real market data → a backtest Universe (guarded; falls back to synthetic).

Two sources, both optional and behind clean guards so the system never stalls:

- **Fundamentals**: the ``edgartools`` library (the same engine as sec-edgar-mcp)
  gives XBRL facts per ticker. We derive the value factors NYX cares about:
  margin of safety, ROIC, debt/equity, owner-earnings yield — as of a filing
  available on/before the backtest date, to limit look-ahead.
- **Forward returns**: a price source (default: Stooq daily CSV) gives the price
  at T and ~1y later, so we can score the realized return the analyst earned.

Resilience is the whole point of this module:

- every network/parse step is wrapped; a bad ticker is skipped, never fatal;
- ``build_universe`` requires a minimum number of clean companies (so a thin or
  garbled feed raises ``DataUnavailable`` instead of yielding a bogus universe
  whose z-scores are meaningless);
- all factor values are validated finite before a Company is admitted;
- ``build_universes`` assembles a multi-date **walk-forward** and tolerates
  individual dates failing;
- if anything is missing (no ``edgartools``, blocked network, sparse data) the
  caller transparently falls back to the deterministic synthetic universe.

The pure logic (parsing, assembly, validation) is unit-tested with injected
fakes, so it is verified even where live data cannot be reached.
"""
from __future__ import annotations

import csv
import io
import math
from dataclasses import dataclass

from .backtest import Company, Universe

MIN_COMPANIES = 5          # below this, z-scores are noise → refuse the universe
MAX_TICKERS = 500          # politeness / cost bound


class DataUnavailable(RuntimeError):
    """Raised when live data can't be fetched (missing lib / blocked / sparse)."""


@dataclass
class RawFundamentals:
    """The minimal inputs we need per company, however they're sourced."""
    ticker: str
    price: float
    intrinsic_value: float
    roic: float
    debt_to_equity: float
    owner_earnings_yield: float


def _finite(*values: float) -> bool:
    return all(isinstance(v, (int, float)) and math.isfinite(v) for v in values)


def fundamentals_to_company(f: RawFundamentals, forward_return: float) -> Company:
    """Validate + normalize raw inputs into a Company, or raise DataUnavailable."""
    if not _finite(f.price, f.intrinsic_value, f.roic, f.debt_to_equity,
                   f.owner_earnings_yield, forward_return):
        raise DataUnavailable(f"non-finite fundamentals for {f.ticker}")
    if f.price <= 0 or f.intrinsic_value <= 0:
        raise DataUnavailable(f"non-positive price/value for {f.ticker}")
    return Company(
        ticker=f.ticker.upper(),
        price=round(f.price, 2),
        intrinsic_value=round(f.intrinsic_value, 2),
        roic=round(f.roic, 4),
        debt_to_equity=round(max(f.debt_to_equity, 0.0), 3),
        owner_earnings_yield=round(f.owner_earnings_yield, 4),
        forward_return=round(forward_return, 4),
    )


# -- fundamentals from EDGAR (optional, point-in-time) ----------------------
def edgar_fundamentals(ticker: str, *, as_of: str = "",
                       identity: str = "") -> RawFundamentals:  # pragma: no cover - live only
    """Derive value factors from edgartools, preferring the latest filing
    on/before ``as_of`` (limits look-ahead). Needs the lib + network + identity."""
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

        fin = None
        if as_of:
            # Prefer the most recent 10-K filed on/before the backtest date.
            try:
                filings = company.get_filings(form="10-K")
                dated = [f for f in filings if str(getattr(f, "filing_date", "")) <= as_of]
                if dated:
                    fin = dated[0].obj().financials
            except Exception:  # noqa: BLE001 — fall back to current financials
                fin = None
        if fin is None:
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
        invested_capital = (equity + total_debt) or 1.0
        return RawFundamentals(
            ticker=ticker.upper(),
            price=mcap or assets,                              # placeholder if no live price
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
def parse_stooq_csv(text: str) -> list[tuple[str, float]]:
    """Parse Stooq daily CSV into sorted (date, close) pairs, dropping junk.

    Resilient to blank lines, ``N/D`` placeholders, missing columns, header
    casing, and non-numeric closes — a malformed row is skipped, not fatal."""
    out: list[tuple[str, float]] = []
    try:
        reader = csv.DictReader(io.StringIO(text))
        for row in reader:
            norm = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
            date, close = norm.get("date", ""), norm.get("close", "")
            if not date or not close or close.upper() in ("N/D", "NA", "NULL"):
                continue
            try:
                price = float(close)
            except ValueError:
                continue
            if math.isfinite(price) and price > 0:
                out.append((date, price))
    except Exception:  # noqa: BLE001 — a garbled document yields no rows, not a crash
        return []
    out.sort(key=lambda x: x[0])   # ascending by ISO date
    return out


def stooq_forward_return(fetcher, ticker: str, *, as_of: str,
                         horizon_days: int = 252) -> float:  # pragma: no cover - live only
    """Realized forward return from Stooq daily CSV via the (allowlisted) fetcher."""
    url = f"https://stooq.com/q/d/l/?s={ticker.lower()}.us&i=d"
    try:
        doc = fetcher.fetch(url)
    except Exception as exc:  # noqa: BLE001
        raise DataUnavailable(f"price fetch failed for {ticker}: {exc}") from exc
    return forward_return_from_series(parse_stooq_csv(doc.text), as_of=as_of,
                                      horizon_days=horizon_days, ticker=ticker)


def forward_return_from_series(series: list[tuple[str, float]], *, as_of: str,
                               horizon_days: int = 252, ticker: str = "") -> float:
    """Compute the ~1y forward return from a sorted (date, close) series."""
    idx = next((i for i, (d, _) in enumerate(series) if d >= as_of), None)
    if idx is None or idx + horizon_days >= len(series):
        raise DataUnavailable(f"insufficient price history for {ticker or 'ticker'}")
    start = series[idx][1]
    end = series[idx + horizon_days][1]
    if start <= 0 or not math.isfinite(end):
        raise DataUnavailable(f"bad price data for {ticker or 'ticker'}")
    return (end - start) / start


# -- assemble a universe -----------------------------------------------------
def build_universe(
    tickers: list[str],
    *,
    as_of: str = "2020-01-02",
    fundamentals_fn=None,
    forward_return_fn=None,
    identity: str = "",
    fetcher=None,
    min_companies: int = MIN_COMPANIES,
) -> Universe:
    """Build one point-in-time Universe. Injectable fns make the logic testable;
    live defaults use EDGAR + Stooq. Raises DataUnavailable if too few clean
    companies load (so a thin/garbled feed never yields a bogus universe)."""
    fundamentals_fn = fundamentals_fn or (lambda t: edgar_fundamentals(t, as_of=as_of,
                                                                        identity=identity))
    forward_return_fn = forward_return_fn or (
        lambda t: stooq_forward_return(fetcher, t, as_of=as_of))

    seen: set[str] = set()
    companies: list[Company] = []
    errors = 0
    for t in tickers[:MAX_TICKERS]:
        key = t.strip().upper()
        if not key or key in seen:
            continue
        seen.add(key)
        try:
            company = fundamentals_to_company(fundamentals_fn(t), forward_return_fn(t))
            companies.append(company)
        except DataUnavailable:
            errors += 1
            continue
    if len(companies) < min_companies:
        raise DataUnavailable(
            f"only {len(companies)} clean companies for {as_of} "
            f"(need {min_companies}; {errors} failures)")
    return Universe(as_of=as_of, companies=companies)


def build_universes(
    tickers: list[str],
    *,
    as_of_dates: tuple[str, ...] = ("2019-01-02", "2020-01-02", "2021-01-04"),
    min_universes: int = 1,
    **kwargs,
) -> list[Universe]:
    """Assemble a multi-date walk-forward. Individual dates may fail (skipped);
    raises DataUnavailable only if fewer than ``min_universes`` succeed."""
    universes: list[Universe] = []
    for as_of in as_of_dates:
        try:
            universes.append(build_universe(tickers, as_of=as_of, **kwargs))
        except DataUnavailable:
            continue
    if len(universes) < min_universes:
        raise DataUnavailable(f"only {len(universes)} universes built "
                              f"(need {min_universes})")
    return universes


def try_build_universes(tickers, **kwargs) -> list[Universe] | None:
    """Best-effort walk-forward: return real universes or None (use synthetic)."""
    try:
        return build_universes(tickers, **kwargs)
    except DataUnavailable:
        return None


def try_build_universe(tickers, **kwargs) -> Universe | None:
    """Best-effort single universe or None (kept for callers/tests)."""
    try:
        return build_universe(tickers, **kwargs)
    except DataUnavailable:
        return None
