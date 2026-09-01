from __future__ import annotations

import pytest

from nyx.capabilities import CapabilityRunner, all_capabilities, select_for
from nyx.domains.investing.backtest import Company
from nyx.domains.investing.data import (
    DataUnavailable,
    RawFundamentals,
    build_universe,
    try_build_universe,
)


def _cfg(tmp_path):
    from nyx.config import load_config

    cfg = load_config(dotenv=False)
    cfg.ledger_path = str(tmp_path / "l.jsonl")
    cfg.memory_path = str(tmp_path / "mem.jsonl")
    cfg.evolution_archive = str(tmp_path / "arch.jsonl")
    cfg.web_cache_dir = str(tmp_path / "wc")
    cfg.max_calls = 400
    cfg.autonomy = "autonomous"
    return cfg


def test_objective_routing():
    select_for("")  # register built-ins
    assert select_for("find me deeply undervalued companies to invest in").name == "value-investing"
    assert select_for("learn from Warren Buffett and Berkshire").name == "value-investing"
    assert select_for("build a billing dashboard").name == "software"
    names = {c.name for c in all_capabilities()}
    assert {"software", "value-investing"} <= names


def test_investing_capability_runs_and_learns(tmp_path):
    cap = select_for("find deep-value undervalued companies, learn from Buffett")
    runner = CapabilityRunner(cap, config=_cfg(tmp_path))
    report = runner.run("find deep-value undervalued companies, learn from Buffett",
                        max_cycles=5, evolve_every=2, generations=8, refresh_every=2)
    # It made decisions, seeded + grew long-term memory, and didn't regress.
    assert len(report.cycles) >= 1
    assert report.long_term_lessons >= 10            # Buffett doctrine seeded
    assert report.evolutions >= 1
    assert report.genome_score_after >= (report.genome_score_before or 0)
    assert report.ledger_ok
    assert all(c.score is not None for c in report.cycles)


def test_software_capability_via_runner(tmp_path):
    from nyx.capabilities.software import SoftwareFactoryCapability

    runner = CapabilityRunner(SoftwareFactoryCapability(), config=_cfg(tmp_path))
    report = runner.run("add a small feature", max_cycles=2, evolve_every=0, refresh_every=0)
    assert len(report.cycles) >= 1
    assert report.ledger_ok


# -- data loader (guarded, logic tested with injected fakes) ----------------
def test_build_universe_with_injected_fakes():
    funds = {
        "AAA": RawFundamentals("AAA", price=50, intrinsic_value=100, roic=0.25,
                               debt_to_equity=0.2, owner_earnings_yield=0.08),
        "BBB": RawFundamentals("BBB", price=120, intrinsic_value=100, roic=0.05,
                               debt_to_equity=1.8, owner_earnings_yield=0.01),
    }
    rets = {"AAA": 0.30, "BBB": -0.15}
    u = build_universe(["AAA", "BBB"], as_of="2020-01-02", min_companies=2,
                       fundamentals_fn=lambda t: funds[t], forward_return_fn=lambda t: rets[t])
    assert len(u.companies) == 2
    aaa = next(c for c in u.companies if c.ticker == "AAA")
    assert isinstance(aaa, Company)
    assert aaa.margin_of_safety == pytest.approx(0.5)
    assert aaa.forward_return == 0.30


def test_screener_widens_universe(monkeypatch):
    """_discover_universe merges SEC-screener tickers into the watchlist, deduped
    and capped, when the edgartools MCP server is available."""
    import json as _json
    from types import SimpleNamespace

    from nyx.domains.investing.capability import ValueInvestingCapability
    from nyx.tools.registry import ToolResult

    monkeypatch.setenv("NYX_INVEST_UNIVERSE_SIZE", "6")
    screened = {"data": {"companies": [
        {"ticker": "AAPL"},        # already in the watchlist → deduped
        {"ticker": "LLY"}, {"ticker": "V"}, {"ticker": "MA"}, {"ticker": "COST"},
    ]}}

    calls = []

    class FakeTools:
        def names(self):
            return ["mcp.edgartools", "web_fetch"]

        def call(self, name, **kwargs):
            calls.append((name, kwargs))
            return ToolResult(ok=True, data=_json.dumps(screened))

    ledger = SimpleNamespace(append=lambda *a, **k: None)
    ctx = SimpleNamespace(toolbox=FakeTools(), ledger=ledger)

    cap = ValueInvestingCapability(tickers=["AAPL", "MSFT"])
    cap._discover_universe(ctx)
    assert calls and calls[0][1]["tool"] == "edgar_screen"
    assert cap.tickers[:2] == ["AAPL", "MSFT"]          # curated names kept first
    assert "LLY" in cap.tickers and cap.tickers.count("AAPL") == 1   # merged + deduped
    assert len(cap.tickers) <= 6                          # capped by NYX_INVEST_UNIVERSE_SIZE
    calls_after_first = len(calls)
    cap._discover_universe(ctx)                           # idempotent: no second screen
    assert len(calls) == calls_after_first


def test_build_universe_raises_when_all_fail():
    def boom(_):
        raise DataUnavailable("no data")

    with pytest.raises(DataUnavailable):
        build_universe(["X"], fundamentals_fn=boom, forward_return_fn=lambda t: 0.0)


def test_try_build_universe_returns_none_on_failure():
    def boom(_):
        raise DataUnavailable("blocked")

    assert try_build_universe(["X"], fundamentals_fn=boom, forward_return_fn=lambda t: 0.0) is None
