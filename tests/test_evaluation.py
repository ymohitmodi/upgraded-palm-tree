"""Standing eval harness: held-out suites, persisted history, trend/delta."""
from __future__ import annotations

from nyx.capabilities.software import SoftwareFactoryCapability
from nyx.domains.investing.backtest import default_universes, heldout_universes
from nyx.evaluation import EvalHarness, _sparkline
from nyx.evolution.benchmarks import default_swebench_suite, heldout_swebench_suite


def _cfg(tmp_path):
    from nyx.config import load_config

    cfg = load_config(dotenv=False)
    cfg.evolution_archive = str(tmp_path / "arch.jsonl")
    cfg.eval_history = str(tmp_path / "evals.jsonl")
    cfg.ledger_path = str(tmp_path / "l.jsonl")
    return cfg


def test_heldout_suites_are_disjoint_from_training():
    train_ids = {t.id for t in default_swebench_suite().tasks}
    held_ids = {t.id for t in heldout_swebench_suite().tasks}
    assert train_ids.isdisjoint(held_ids)                 # no task overlap

    train_seeds = {u.as_of for u in default_universes()}
    held_seeds = {u.as_of for u in heldout_universes()}
    assert train_seeds.isdisjoint(held_seeds)             # no period overlap


def test_capability_eval_returns_scores(tmp_path):
    cfg = _cfg(tmp_path)
    from nyx.providers.mock import MockProvider

    sw = SoftwareFactoryCapability().eval(cfg, MockProvider(cfg))
    assert sw is not None and 0.0 <= sw.score <= 1.0
    from nyx.capabilities.registry import get

    inv = get("value-investing").eval(cfg, MockProvider(cfg))
    assert inv is not None and isinstance(inv.score, float)


def test_advisor_is_not_objectively_scored(tmp_path):
    from nyx.capabilities.registry import get

    assert get("advisor").eval(_cfg(tmp_path), None) is None


def test_harness_records_history_and_delta(tmp_path):
    harness = EvalHarness(_cfg(tmp_path))
    first = harness.run_all()
    assert first and all(r.score is not None for r in first)
    # A second run appends a second point; delta is computed vs the previous.
    harness.run_all()
    for cap in {r.capability for r in first}:
        assert len(harness.history(cap)) == 2
        assert harness.delta(cap) is not None          # numeric (0.0 if unchanged)
    # First-ever eval has no delta.
    fresh = EvalHarness(_cfg(tmp_path / "x"))
    fresh.path.parent.mkdir(exist_ok=True)
    fresh.run_all()
    assert fresh.delta("software") is None


def test_sparkline_renders():
    assert _sparkline([0.1, 0.5, 0.9])
    assert _sparkline([]) == ""
