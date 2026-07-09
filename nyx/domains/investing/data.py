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
import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone

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
def _num(v) -> float:
    """Coerce an edgartools value to a finite float (None/NaN/junk → 0.0)."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return 0.0
    return f if math.isfinite(f) else 0.0


def _financials_as_of(company, as_of: str):  # pragma: no cover - live only
    """Prefer the most recent 10-K filed on/before ``as_of`` (limits look-ahead);
    fall back to the company's latest financials."""
    if as_of:
        try:
            filings = company.get_filings(form="10-K")
            dated = [f for f in filings if str(getattr(f, "filing_date", "")) <= as_of]
            if dated:
                fin = dated[0].obj().financials
                if fin is not None:
                    return fin
        except Exception:  # noqa: BLE001 — fall back to current financials
            pass
    return company.get_financials()


def price_at(series: list[tuple[str, float]], as_of: str) -> float:
    """Latest close on/before ``as_of`` from a sorted (date, close) series."""
    price = 0.0
    for d, c in series:
        if d <= as_of:
            price = c
        else:
            break
    return price


# -- price history from Yahoo Finance (Stooq is now behind a JS anti-bot wall) --
def _epoch(date_str: str) -> int:
    return int(datetime.strptime(date_str, "%Y-%m-%d")
               .replace(tzinfo=timezone.utc).timestamp())


def parse_yahoo_chart(text: str) -> list[tuple[str, float]]:
    """Parse a Yahoo Finance v8 chart JSON payload into sorted (date, close) pairs.

    Prefers split/dividend-adjusted closes; resilient to nulls and missing keys —
    a malformed payload yields an empty series, never an exception."""
    try:
        result = json.loads(text)["chart"]["result"][0]
        stamps = result["timestamp"]
        ind = result["indicators"]
        closes = None
        if ind.get("adjclose"):
            closes = ind["adjclose"][0].get("adjclose")
        if not closes:
            closes = ind["quote"][0].get("close")
    except (KeyError, IndexError, TypeError, ValueError):
        return []
    out: list[tuple[str, float]] = []
    for t, c in zip(stamps, closes or []):
        if c is None:
            continue
        try:
            price = float(c)
        except (TypeError, ValueError):
            continue
        if math.isfinite(price) and price > 0:
            day = datetime.fromtimestamp(t, tz=timezone.utc).strftime("%Y-%m-%d")
            out.append((day, price))
    out.sort(key=lambda x: x[0])
    return out


def yahoo_price_series(fetcher, ticker: str, *, start: str = "2015-01-01",
                       end: str = "2027-01-01") -> list[tuple[str, float]]:  # pragma: no cover - live
    """Daily adjusted-close series for a US ticker. One wide-range fetch per
    ticker (cached by the fetcher) serves both the as-of price and the forward
    return, so there is a single network round-trip per name."""
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker.upper()}"
           f"?period1={_epoch(start)}&period2={_epoch(end)}&interval=1d")
    return parse_yahoo_chart(fetcher.fetch(url).text)


def market_price_at(fetcher, ticker: str, as_of: str) -> float:  # pragma: no cover - live only
    """The market price on/before ``as_of`` (for market cap / margin of safety)."""
    p = price_at(yahoo_price_series(fetcher, ticker), as_of)
    if p <= 0:
        raise DataUnavailable(f"no price on/before {as_of} for {ticker}")
    return p


def market_forward_return(fetcher, ticker: str, *, as_of: str,
                          horizon_days: int = 252) -> float:  # pragma: no cover - live only
    """Realized ~1y forward return from the Yahoo daily series (same cached fetch
    as the price), so the analyst's picks are scored on real outcomes."""
    return forward_return_from_series(yahoo_price_series(fetcher, ticker), as_of=as_of,
                                      horizon_days=horizon_days, ticker=ticker)


def edgar_fundamentals(ticker: str, *, as_of: str = "", identity: str = "",
                       fetcher=None) -> RawFundamentals:  # pragma: no cover - live only
    """Derive value factors from edgartools (real accessors), preferring the 10-K
    filed on/before ``as_of``. Market cap comes from the market price (Stooq) ×
    diluted shares, since EDGAR carries no price. Needs the lib + network + a
    valid ``EDGAR_IDENTITY`` and a ``fetcher`` for the price."""
    try:
        import edgar  # type: ignore
    except ImportError as exc:
        raise DataUnavailable("edgartools not installed (pip install 'edgartools[ai]')") from exc
    import os

    ident = identity or os.environ.get("EDGAR_IDENTITY", "")
    if not ident:
        raise DataUnavailable("EDGAR_IDENTITY not set")
    if fetcher is None:
        raise DataUnavailable("no price source (fetcher) provided")
    try:
        edgar.set_identity(ident)
        company = edgar.Company(ticker)
        fin = _financials_as_of(company, as_of)

        net_income = _num(fin.get_net_income())
        total_assets = _num(fin.get_total_assets())
        total_liabilities = _num(fin.get_total_liabilities())
        equity = _num(fin.get_stockholders_equity()) or (total_assets - total_liabilities)
        current_liabilities = _num(fin.get_current_liabilities())
        op_cf = _num(fin.get_operating_cash_flow())
        capex = abs(_num(fin.get_capital_expenditures()))
        fcf = _num(fin.get_free_cash_flow())
        shares = (_num(fin.get_shares_outstanding_diluted())
                  or _num(fin.get_shares_outstanding_basic()))
        if shares <= 0:
            raise DataUnavailable(f"no diluted share count for {ticker}")

        # Owner-earnings (distributable cash): prefer reported FCF, then
        # operating cash flow minus capex, then net income as a conservative floor.
        if fcf:
            owner_earnings = fcf
        elif op_cf:
            owner_earnings = op_cf - capex
        else:
            owner_earnings = net_income

        market_cap = market_price_at(fetcher, ticker, as_of or "9999-12-31") * shares
        equity = equity or 1.0
        # Leverage proxy: long-term liabilities (total minus current) to equity —
        # excludes operating payables so it reads closer to true debt.
        debt = max(total_liabilities - current_liabilities, 0.0) or total_liabilities
        invested_capital = (equity + debt) or 1.0
        return RawFundamentals(
            ticker=ticker.upper(),
            price=market_cap,
            intrinsic_value=max(owner_earnings, 0.0) * 12.0,   # conservative 12x owner-earnings
            roic=net_income / invested_capital,
            debt_to_equity=debt / equity,
            owner_earnings_yield=(owner_earnings / market_cap) if market_cap else 0.0,
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
    fundamentals_fn = fundamentals_fn or (
        lambda t: edgar_fundamentals(t, as_of=as_of, identity=identity, fetcher=fetcher))
    forward_return_fn = forward_return_fn or (
        lambda t: market_forward_return(fetcher, t, as_of=as_of))

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
