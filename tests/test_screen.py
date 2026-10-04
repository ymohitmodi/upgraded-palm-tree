"""The as-of-today screen: shared ranking, forward-return-free universe, and the
judgment layer that turns read filings into a shortlist."""
from __future__ import annotations

from nyx.domains.investing.assess import Assessment, assess_company, rank_assessments
from nyx.domains.investing.backtest import Company, Universe, composite_rank
from nyx.domains.investing.data import RawFundamentals, build_current_universe, today

_EQUAL = {"mos": 1.0, "roic": 1.0, "debt": 1.0, "oey": 1.0}


def _co(ticker, *, price, iv, roic, dte, oey, fwd=0.0):
    return Company(ticker=ticker, price=price, intrinsic_value=iv, roic=roic,
                   debt_to_equity=dte, owner_earnings_yield=oey, forward_return=fwd)


def test_composite_rank_prefers_cheap_quality_low_debt():
    universe = Universe(as_of="T", companies=[
        _co("CHEAP", price=50, iv=100, roic=0.25, dte=0.2, oey=0.10),   # best on all four
        _co("MID", price=90, iv=100, roic=0.15, dte=1.0, oey=0.05),
        _co("RICH", price=140, iv=100, roic=0.05, dte=2.2, oey=0.01),   # worst on all four
    ])
    ranked = composite_rank(universe, _EQUAL)
    assert [c.ticker for _, c in ranked] == ["CHEAP", "MID", "RICH"]
    assert ranked[0][0] > ranked[-1][0]          # composite score is ordered


def test_composite_rank_penalizes_leverage():
    """Same cheapness/quality; the levered name must rank lower (debt has a minus)."""
    universe = Universe(as_of="T", companies=[
        _co("SAFE", price=50, iv=100, roic=0.2, dte=0.1, oey=0.06),
        _co("LEVERED", price=50, iv=100, roic=0.2, dte=3.0, oey=0.06),
    ])
    ranked = composite_rank(universe, _EQUAL)
    assert [c.ticker for _, c in ranked] == ["SAFE", "LEVERED"]


# -- as-of-today universe: no forward return exists yet ----------------------
def test_build_current_universe_has_no_forward_return_and_dates_today():
    def fund(t):
        base = sum(ord(c) for c in t)
        return RawFundamentals(t, price=50 + base % 40, intrinsic_value=100,
                               roic=0.1, debt_to_equity=0.5, owner_earnings_yield=0.05)

    u = build_current_universe(["AAA", "BBB", "CCC"], fundamentals_fn=fund, min_companies=3)
    assert u.as_of == today()
    assert all(c.forward_return == 0.0 for c in u.companies)   # unknowable, never scored
    assert len(u.companies) == 3


# -- judgment layer ----------------------------------------------------------
def test_assess_company_offline_is_neutral_and_says_so():
    a = assess_company(None, None, ticker="KO", factor_score=1.2, metrics="m",
                       principles="p", evidence="e")
    assert a.llm_score == 5.0                      # neutral — no fabricated opinion
    assert "offline" in a.rationale
    assert a.ticker == "KO" and a.factor_score == 1.2


def test_rank_assessments_blends_conviction_and_factors():
    items = [
        Assessment(ticker="A", factor_score=0.0, llm_score=10.0),   # loved, weak factors
        Assessment(ticker="B", factor_score=2.0, llm_score=0.0),    # strong factors, disliked
    ]
    ranked = rank_assessments(items, judgment_weight=0.6)
    assert ranked[0].ticker == "A"                 # judgment carries 60% of the blend
    flipped = rank_assessments(items, judgment_weight=0.2)
    assert flipped[0].ticker == "B"                # tilt to factors and B wins
    assert all(0.0 <= a.final_score <= 1.0 for a in ranked)


def test_rank_assessments_is_stable_when_all_scores_tie():
    items = [Assessment(ticker=t, factor_score=1.0, llm_score=5.0) for t in ("X", "Y")]
    ranked = rank_assessments(items)
    assert {a.ticker for a in ranked} == {"X", "Y"}
    assert all(a.final_score == 0.5 for a in ranked)   # min-max of a tie → 0.5, no NaN
