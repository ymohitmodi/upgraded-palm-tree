from __future__ import annotations

import pytest

from nyx.domains.investing.backtest import Company, Universe
from nyx.domains.investing.data import (
    DataUnavailable,
    RawFundamentals,
    build_universe,
    build_universes,
    forward_return_from_series,
    fundamentals_to_company,
    parse_stooq_csv,
    try_build_universes,
)


# -- resilient Stooq CSV parsing --------------------------------------------
def test_parse_stooq_csv_survives_garbage():
    csv_text = (
        "Date,Open,High,Low,Close,Volume\n"
        "2020-01-02,10,11,9,10.50,1000\n"
        "\n"                                   # blank line
        "2020-01-03,,,,,N/D\n"                 # N/D close → skip
        "2020-01-06,10,11,9,not_a_number,5\n"  # non-numeric → skip
        "2020-01-07,10,11,9,11.25,900\n"
    )
    series = parse_stooq_csv(csv_text)
    assert series == [("2020-01-02", 10.5), ("2020-01-07", 11.25)]
    assert parse_stooq_csv("total garbage not csv") == []      # never raises


def test_forward_return_from_series():
    series = [(f"2020-01-{d:02d}", 100.0 + d) for d in range(1, 20)]
    r = forward_return_from_series(series, as_of="2020-01-02", horizon_days=5)
    assert r == pytest.approx(((100 + 7) - (100 + 2)) / (100 + 2))
    with pytest.raises(DataUnavailable):        # not enough history ahead
        forward_return_from_series(series, as_of="2020-01-18", horizon_days=252)


# -- validation / format resilience -----------------------------------------
def test_fundamentals_to_company_rejects_bad_values():
    good = RawFundamentals("AAA", price=50, intrinsic_value=100, roic=0.2,
                           debt_to_equity=0.3, owner_earnings_yield=0.05)
    assert isinstance(fundamentals_to_company(good, 0.1), Company)
    for bad in (
        RawFundamentals("B", price=0, intrinsic_value=100, roic=0.1, debt_to_equity=0.1,
                        owner_earnings_yield=0.1),                       # non-positive price
        RawFundamentals("C", price=float("nan"), intrinsic_value=100, roic=0.1,
                        debt_to_equity=0.1, owner_earnings_yield=0.1),   # non-finite
    ):
        with pytest.raises(DataUnavailable):
            fundamentals_to_company(bad, 0.1)


# -- universe assembly (injected fns; no network) ---------------------------
def _fund(t):
    base = sum(ord(c) for c in t)
    return RawFundamentals(t, price=50 + base % 50, intrinsic_value=100,
                           roic=0.05 + (base % 20) / 100, debt_to_equity=(base % 3),
                           owner_earnings_yield=(base % 10) / 100)


def test_build_universe_requires_minimum_companies():
    tickers = [f"T{i}" for i in range(8)]

    # Everything fails → DataUnavailable, not a bogus universe.
    def boom(_):
        raise DataUnavailable("x")

    with pytest.raises(DataUnavailable):
        build_universe(tickers, fundamentals_fn=boom, forward_return_fn=lambda t: 0.1)

    # Too few clean companies → refused (z-scores would be noise).
    def only_two(t):
        if t in ("T0", "T1"):
            return _fund(t)
        raise DataUnavailable("skip")

    with pytest.raises(DataUnavailable):
        build_universe(tickers, fundamentals_fn=only_two, forward_return_fn=lambda t: 0.1,
                       min_companies=5)


def test_build_universe_dedups_and_admits_clean_set():
    tickers = ["AAA", "aaa", "BBB", "CCC", "DDD", "EEE", "FFF"]  # dup AAA/aaa
    u = build_universe(tickers, fundamentals_fn=_fund,
                       forward_return_fn=lambda t: 0.1, min_companies=5)
    seen = [c.ticker for c in u.companies]
    assert seen.count("AAA") == 1 and len(u.companies) == 6      # deduped


def test_build_universes_walk_forward_tolerates_failing_dates():
    tickers = [f"T{i}" for i in range(8)]
    good = {"2020-01-02", "2021-01-04"}

    def fwd_for(as_of):
        if as_of not in good:
            def fail(_):
                raise DataUnavailable("no prices this date")
            return fail
        return lambda t: 0.12

    # Simulate per-date price availability by wrapping build_universe calls.
    universes = build_universes(
        tickers, as_of_dates=("2018-01-02", "2020-01-02", "2021-01-04"),
        fundamentals_fn=_fund,
        forward_return_fn=lambda t: 0.12,   # fundamentals ok for all
        min_universes=1,
    )
    assert isinstance(universes, list) and len(universes) == 3
    assert all(isinstance(u, Universe) and len(u.companies) >= 5 for u in universes)


def test_try_build_universes_returns_none_on_total_failure():
    def boom(_):
        raise DataUnavailable("blocked")

    assert try_build_universes(["X", "Y"], fundamentals_fn=boom,
                               forward_return_fn=lambda t: 0.0) is None
