from __future__ import annotations

from nyx.agents.base import Genome
from nyx.constitution import Constitution
from nyx.domains.investing import (
    ValueBenchmark,
    check_investing,
    default_universe,
    investing_constitution,
)
from nyx.domains.investing.backtest import INVESTING_DIRECTIVES, genome_factor_weights


def _genome(text: str) -> Genome:
    return Genome(role="analyst", system_prompt=text, model_role="architect")


def test_universe_is_deterministic():
    u1 = default_universe()
    u2 = default_universe()
    assert [c.ticker for c in u1.companies] == [c.ticker for c in u2.companies]
    assert u1.companies[0].forward_return == u2.companies[0].forward_return


def test_value_doctrine_beats_naive_genome():
    """A genome encoding the value doctrine should backtest better than a blank one
    — i.e., the fitness signal actually rewards sound investing principles."""
    bench = ValueBenchmark()
    naive = bench.evaluate(_genome("You pick stocks."))
    doctrine = bench.evaluate(_genome(
        "Demand a margin of safety vs intrinsic value; prize ROIC and moats; "
        "penalize debt and leverage; value owner-earnings, not EPS."
    ))
    assert doctrine.score > naive.score


def test_genome_weights_shift_with_doctrine():
    w = genome_factor_weights(_genome("margin of safety, roic, debt, owner-earnings"))
    assert w["mos"] >= 1.0 and w["roic"] >= 1.0 and w["debt"] >= 1.0 and w["oey"] >= 1.0
    # A charter that emphasizes a factor more heavily earns a higher weight.
    heavy = genome_factor_weights(_genome(
        "margin of safety; undervalued; buy cheap below intrinsic value"))
    assert heavy["mos"] > w["mos"]


def test_value_benchmark_plugs_into_evolution():
    """Evolving the analyst against the value backtest should not regress and
    should keep the doctrine in-role."""
    from nyx.config import load_config
    from nyx.evolution.archive import Archive
    from nyx.evolution.engine import EvolutionEngine

    cfg = load_config(dotenv=False)
    import tempfile

    cfg.evolution_archive = tempfile.mkdtemp() + "/archive.jsonl"
    cfg.ledger_path = tempfile.mkdtemp() + "/l.jsonl"
    const = Constitution.load(cfg.constitution_path, mode=cfg.constitution_mode)
    engine = EvolutionEngine(
        config=cfg, constitution=const, archive=Archive(cfg.evolution_archive),
        role="analyst", benchmark=ValueBenchmark(), directive_pool=INVESTING_DIRECTIVES,
    )
    report = engine.evolve(generations=12)
    assert report.best_score_after >= report.best_score_before
    assert report.best_genome.get("role") == "analyst"


def test_investing_gates_catch_violations():
    assert check_investing("Buy SYN1 now — guaranteed risk-free 30% return!")
    # A sound, sourced, margin-of-safety thesis passes.
    good = ("Recommend SYN1: trades at a 35% margin of safety to intrinsic value "
            "per its 10-K; ROIC 22%, low debt. Source: SEC EDGAR filing.")
    assert check_investing(good) == []


def test_investing_constitution_blocks_guarantees():
    const = investing_constitution()
    verdict = const.evaluate("operate", "We guarantee a risk-free profit to investors.", {"audited": True})
    assert not verdict.passed
