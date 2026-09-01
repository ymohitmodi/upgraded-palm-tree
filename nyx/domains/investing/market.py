"""Full-market screen — the funnel's wide mouth, over *every* SEC filer.

Reading a full 10-K for all ~7,600 companies is infeasible (hundreds of thousands
of model calls). Real analysts funnel: screen the whole market cheaply on quality,
then deep-read only the finalists. SEC's bulk endpoints make the wide pass fast —
the whole market's fundamentals arrive in ~7 calls, not 7,600:

- ``company_tickers.json`` — every ticker↔CIK (one fetch, ~9k companies).
- XBRL **frames** (``/api/xbrl/frames/us-gaap/<concept>/USD/<period>.json``) — one
  concept for *all* filers in a single call. Balance-sheet concepts are instant
  (period ``CY<yyyy>Q4I``); income/flow concepts span the year (``CY<yyyy>``).

This stage uses **no market price** (fetching 9k quotes would defeat the point):
it ranks on price-free quality — ROIC, low leverage, owner-earnings on equity —
so only the strongest few hundred survive to the valuation + deep-read stage.

Everything flows through NYX's egress-guarded, cached ``WebFetcher`` (so SSRF
policy and rate limiting still apply) and reuses the backtest's ``Company`` and
``composite_rank`` — no parallel data or ranking machinery.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone

from .backtest import Company, Universe
from .data import _num

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
FRAMES = "https://data.sec.gov/api/xbrl/frames/us-gaap/{concept}/USD/{period}.json"

# concept -> True if it is a balance-sheet (instantaneous) fact.
_CONCEPTS = {
    "NetIncomeLoss": False,
    "Assets": True,
    "StockholdersEquity": True,
    "Liabilities": True,
    "LiabilitiesCurrent": True,
    "NetCashProvidedByUsedInOperatingActivities": False,
    "PaymentsToAcquirePropertyPlantAndEquipment": False,
}


@dataclass
class MarketRow:
    cik: int
    ticker: str
    name: str
    net_income: float
    assets: float
    equity: float
    liabilities: float
    current_liabilities: float
    operating_cash_flow: float
    capex: float

    @property
    def owner_earnings(self) -> float:
        oe = self.operating_cash_flow - abs(self.capex)
        return oe if oe != 0 else self.net_income

    @property
    def total_liabilities(self) -> float:
        # Many filers don't tag a single `Liabilities`; derive it from the
        # accounting identity (assets − equity) so leverage isn't falsely zero.
        if self.liabilities > 0:
            return self.liabilities
        return max(self.assets - self.equity, 0.0)

    @property
    def roa(self) -> float:
        # Assets-denominated: stable and well-reported. Equity-based ROIC explodes
        # for buyback-heavy firms with tiny/negative book equity — a false signal.
        return self.net_income / (self.assets or 1.0)

    @property
    def leverage(self) -> float:
        return self.total_liabilities / (self.assets or 1.0)   # 0..1, comparable

    @property
    def owner_earnings_on_assets(self) -> float:
        return self.owner_earnings / (self.assets or 1.0)

    # Kept for compatibility/inspection; not used by the (assets-based) screen.
    @property
    def debt_to_equity(self) -> float:
        return self.total_liabilities / (self.equity or 1.0)


def _get_json(fetcher, url: str):
    """Fetch JSON through the egress-guarded fetcher (raw, not HTML-reduced)."""
    doc = fetcher.fetch(url, as_text=False)
    if not (200 <= doc.status < 300):
        raise RuntimeError(f"HTTP {doc.status} for {url}")
    return json.loads(doc.text)


def all_companies(fetcher) -> dict[int, dict]:  # pragma: no cover - live only
    """Every SEC filer: ``{cik: {'ticker','name'}}`` (one fetch)."""
    raw = _get_json(fetcher, TICKERS_URL)
    rows = raw.values() if isinstance(raw, dict) else raw
    out: dict[int, dict] = {}
    for r in rows:
        cik = int(r.get("cik_str") or r.get("cik") or 0)
        ticker = str(r.get("ticker") or "").strip().upper()
        if cik and ticker:
            out[cik] = {"ticker": ticker, "name": r.get("title") or r.get("name") or ""}
    return out


def bulk_concept(fetcher, concept: str, year: int) -> dict[int, float]:  # pragma: no cover - live
    """One XBRL concept for the whole market: ``{cik: value}`` (one call)."""
    period = f"CY{year}Q4I" if _CONCEPTS.get(concept) else f"CY{year}"
    try:
        data = _get_json(fetcher, FRAMES.format(concept=concept, period=period)).get("data", [])
    except Exception:  # noqa: BLE001 — a missing frame degrades gracefully to {}
        return {}
    out: dict[int, float] = {}
    for row in data:
        try:
            out[int(row["cik"])] = float(row["val"])
        except (KeyError, TypeError, ValueError):
            continue
    return out


def latest_full_year() -> int:
    """The most recent year whose annual XBRL frames are reliably populated.

    Annual (CY) frames for a fiscal year fill in over the following spring as 10-Ks
    are filed, so target two years back until well into the next year."""
    now = datetime.now(tz=timezone.utc)
    return now.year - 1 if now.month >= 6 else now.year - 2


def load_market(fetcher, *, year: int | None = None,
                min_rows: int = 800) -> list[MarketRow]:  # pragma: no cover - live only
    """Assemble the whole market's fundamentals from bulk frames (~7 calls).

    ``year=None`` auto-selects the latest well-populated year, stepping back if a
    year's frames haven't filled in yet."""
    if year is not None:
        return _load_market_year(fetcher, year)
    start = latest_full_year()
    best: list[MarketRow] = []
    for candidate in (start, start - 1, start - 2):
        rows = _load_market_year(fetcher, candidate)
        if len(rows) >= min_rows:
            return rows
        if len(rows) > len(best):
            best = rows
    return best


def _load_market_year(fetcher, year: int) -> list[MarketRow]:  # pragma: no cover - live only
    companies = all_companies(fetcher)
    frames = {c: bulk_concept(fetcher, c, year) for c in _CONCEPTS}
    rows: list[MarketRow] = []
    for cik, meta in companies.items():
        ni = frames["NetIncomeLoss"].get(cik)
        eq = frames["StockholdersEquity"].get(cik)
        if ni is None or eq is None:      # need at least earnings + equity to judge
            continue
        rows.append(MarketRow(
            cik=cik, ticker=meta["ticker"], name=meta["name"],
            net_income=_num(ni), assets=_num(frames["Assets"].get(cik)),
            equity=_num(eq), liabilities=_num(frames["Liabilities"].get(cik)),
            current_liabilities=_num(frames["LiabilitiesCurrent"].get(cik)),
            operating_cash_flow=_num(frames["NetCashProvidedByUsedInOperatingActivities"].get(cik)),
            capex=_num(frames["PaymentsToAcquirePropertyPlantAndEquipment"].get(cik)),
        ))
    return rows


def _z(values: list[float]) -> list[float]:
    n = len(values) or 1
    mean = sum(values) / n
    sd = (sum((v - mean) ** 2 for v in values) / n) ** 0.5 or 1.0
    return [(v - mean) / sd for v in values]


def is_sound(row: MarketRow, *, min_assets: float = 1e8) -> bool:
    """Sound-business filter: profitable, real size, and sane assets-based factors
    (rejects XBRL-tag outliers that would otherwise dominate the ranking)."""
    return (row.net_income > 0 and row.equity > 0 and row.assets > min_assets
            and math.isfinite(row.roa) and math.isfinite(row.leverage)
            and math.isfinite(row.owner_earnings_on_assets)
            and 0.0 < row.roa < 0.6 and 0.0 <= row.leverage < 1.2
            and -0.5 < row.owner_earnings_on_assets < 0.6)


def quality_screen(rows: list[MarketRow], *, top_n: int = 200,
                   min_assets: float = 1e8) -> list[MarketRow]:
    """Rank the whole market on price-free quality and keep the top ``top_n``.

    Sound-business filters first, then a z-scored composite: high return on assets,
    high owner-earnings on assets, low leverage — the durable-quality half of the
    Buffett doctrine that needs no price. Valuation (margin of safety) is applied
    later, on the survivors, once real prices are fetched.
    """
    ok = [r for r in rows if is_sound(r, min_assets=min_assets)]
    if not ok:
        return []
    z_roa = _z([r.roa for r in ok])
    z_oea = _z([r.owner_earnings_on_assets for r in ok])
    z_lev = _z([r.leverage for r in ok])
    scored = sorted(
        zip(ok, (zr + zo - zl for zr, zo, zl in zip(z_roa, z_oea, z_lev))),
        key=lambda x: x[1], reverse=True,
    )
    return [r for r, _ in scored[:top_n]]


def market_universe_tickers(fetcher, *, year: int | None = None, top_n: int = 200,
                            min_assets: float = 1e8) -> list[str]:  # pragma: no cover - live
    """The funnel's stage-1 output: the top-quality tickers across the whole market."""
    return [r.ticker for r in quality_screen(load_market(fetcher, year=year),
                                             top_n=top_n, min_assets=min_assets)]


def rows_to_universe(rows: list[MarketRow]) -> Universe:
    """Adapt quality rows to a price-free ``Universe`` (for inspection/tests).

    Price is unknown here, so margin of safety is neutralized (price == intrinsic);
    only the quality factors carry signal. The valuation stage rebuilds these names
    with real prices via ``build_current_universe``.
    """
    companies = [
        Company(ticker=r.ticker, price=1.0, intrinsic_value=1.0,
                roic=round(r.roa, 4), debt_to_equity=round(max(r.leverage, 0.0), 3),
                owner_earnings_yield=round(r.owner_earnings_on_assets, 4))
        for r in rows
    ]
    return Universe(as_of="market", companies=companies)
