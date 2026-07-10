"""Full-market quality screen — the funnel's wide stage (logic tested offline)."""
from __future__ import annotations

from nyx.domains.investing.market import MarketRow, is_sound, quality_screen, rows_to_universe


def _row(ticker, *, ni, assets, equity, liab, cur_liab=0.0, ocf=0.0, capex=0.0):
    return MarketRow(cik=hash(ticker) % 10**6, ticker=ticker, name=ticker,
                     net_income=ni, assets=assets, equity=equity, liabilities=liab,
                     current_liabilities=cur_liab, operating_cash_flow=ocf, capex=capex)


def test_assets_based_factors_are_stable_for_thin_equity():
    """A buyback-heavy firm with tiny book equity must NOT show an absurd ROIC —
    assets-based ROA stays sane where equity-based ROIC would explode."""
    r = _row("THIN", ni=5e9, assets=50e9, equity=1e8, liab=40e9, cur_liab=10e9)
    assert 0.0 < r.roa < 0.6                       # 5B / 50B = 10%
    assert r.roa == 0.1
    assert r.leverage == 40e9 / 50e9               # liabilities / assets


def test_total_liabilities_derived_when_untagged():
    """Missing `Liabilities` tag → derive from assets − equity (not a false zero)."""
    r = _row("NOLIAB", ni=1e9, assets=10e9, equity=4e9, liab=0.0)
    assert r.total_liabilities == 6e9              # 10B − 4B
    assert r.leverage == 0.6


def test_owner_earnings_prefers_cashflow_then_net_income():
    r = _row("CF", ni=1e9, assets=10e9, equity=5e9, liab=5e9, ocf=3e9, capex=1e9)
    assert r.owner_earnings == 2e9                 # ocf − capex
    r2 = _row("NOCF", ni=1e9, assets=10e9, equity=5e9, liab=5e9)
    assert r2.owner_earnings == 1e9                # falls back to net income


def test_is_sound_rejects_losers_and_outliers():
    good = _row("GOOD", ni=2e9, assets=20e9, equity=8e9, liab=12e9, ocf=3e9, capex=1e9)
    assert is_sound(good)
    assert not is_sound(_row("LOSS", ni=-1e9, assets=20e9, equity=8e9, liab=12e9))   # unprofitable
    assert not is_sound(_row("TINY", ni=1e6, assets=1e6, equity=5e5, liab=5e5))       # sub-scale
    assert not is_sound(_row("OUTLIER", ni=9e9, assets=10e9, equity=5e9, liab=5e9))   # ROA 90% → bad tag


def test_quality_screen_ranks_and_bounds():
    rows = [
        _row("BEST", ni=4e9, assets=20e9, equity=12e9, liab=8e9, ocf=5e9, capex=1e9),   # high ROA, low lev
        _row("MEH", ni=1e9, assets=20e9, equity=6e9, liab=14e9, ocf=1.5e9, capex=0.5e9),
        _row("WEAK", ni=5e8, assets=25e9, equity=3e9, liab=22e9, ocf=6e8, capex=2e8),   # low ROA, high lev
        _row("LOSS", ni=-2e9, assets=20e9, equity=8e9, liab=12e9),                       # filtered out
    ]
    top = quality_screen(rows, top_n=2, min_assets=1e8)
    assert [r.ticker for r in top] == ["BEST", "MEH"]     # ranked; loser excluded; bounded to 2


def test_rows_to_universe_maps_assets_based_factors():
    rows = [_row("A", ni=2e9, assets=20e9, equity=10e9, liab=10e9, ocf=3e9, capex=1e9)]
    u = rows_to_universe(rows)
    c = u.companies[0]
    assert c.ticker == "A" and c.roic == 0.1           # ROA surfaced as the quality factor
    assert c.price == c.intrinsic_value                # price-free: MoS neutralized
