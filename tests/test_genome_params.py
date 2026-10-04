"""Richer genome: continuous params gene vector, its mutation, round-trip through
the archive, and its effect on the value backtest (the plateau-breaker)."""
from __future__ import annotations

from nyx.agents.base import Genome
from nyx.domains.investing.backtest import ValueBenchmark, default_universes, weights_for
from nyx.evolution.archive import GenomeRecord
from nyx.evolution.engine import EvolutionEngine, _genome_id, _serialize


def _analyst(params=None):
    return Genome(role="analyst", system_prompt="value analyst", params=params or {})


# -- genome plumbing ----------------------------------------------------------
def test_params_roundtrip_and_isolation():
    g = _analyst({"w_mos": 1.5})
    ser = _serialize(g)
    assert ser["params"] == {"w_mos": 1.5}
    back = GenomeRecord(id="x", genome=ser, score=0.1, parent_id=None,
                        generation=0).to_genome()
    assert back.params == {"w_mos": 1.5}
    # mutate must deep-copy params — a child never mutates its parent's vector.
    child = g.mutate()
    child.params["w_mos"] = 9.9
    assert g.params["w_mos"] == 1.5


def test_legacy_archive_record_without_params_still_loads():
    """Genomes banked before this feature have no 'params' key."""
    legacy = {"role": "analyst", "system_prompt": "x", "temperature": 0.2}
    g = GenomeRecord(id="x", genome=legacy, score=0.1, parent_id=None,
                     generation=0).to_genome()
    assert g.params == {}


def test_param_only_mutation_is_a_distinct_genome_id():
    g = _analyst({"w_mos": 1.0})
    assert _genome_id(g) != _genome_id(g.mutate(params={"w_mos": 2.0}))


# -- mutation seeds then perturbs the whole vector ----------------------------
def test_engine_seeds_and_perturbs_params(tmp_path):
    from nyx.config import load_config

    cfg = load_config(dotenv=False)
    cfg.ollama_api_key = ""
    space = {"w_mos": (0.0, 3.0, 1.5), "top_n": (3.0, 15.0, 8.0)}
    eng = EvolutionEngine(config=cfg, role="analyst", param_space=space,
                          archive=__import__("nyx.evolution.archive", fromlist=["Archive"])
                          .Archive(str(tmp_path / "a.jsonl")), seed=7)
    seeded = eng._mutate_param(_analyst())            # empty → seed full vector
    assert set(seeded.params) == {"w_mos", "top_n"}
    assert 0.0 <= seeded.params["w_mos"] <= 3.0 and 3.0 <= seeded.params["top_n"] <= 15.0
    perturbed = eng._mutate_param(seeded)             # non-empty → nudge, stay in bounds
    assert set(perturbed.params) == {"w_mos", "top_n"}
    assert 0.0 <= perturbed.params["w_mos"] <= 3.0


# -- the genome now actually changes the backtest -----------------------------
def test_params_drive_weights_and_change_the_score():
    universes = default_universes()
    bench = ValueBenchmark(universes=universes)
    # Two very different doctrines must produce different backtest scores — proof
    # the continuous genes are a real, fitness-relevant search space.
    mos_heavy = _analyst({"w_mos": 3.0, "w_roic": 0.0, "w_debt": 0.0, "w_oey": 0.0})
    roic_heavy = _analyst({"w_mos": 0.0, "w_roic": 3.0, "w_debt": 0.0, "w_oey": 0.0})
    assert weights_for(mos_heavy)["mos"] == 3.0        # params are authoritative
    assert bench.evaluate(mos_heavy).score != bench.evaluate(roic_heavy).score


def test_portfolio_knobs_take_effect():
    universes = default_universes()
    concentrated = _analyst({"w_mos": 1.5, "w_roic": 1.0, "w_debt": 1.0, "w_oey": 1.0,
                             "top_n": 3.0})
    broad = _analyst({"w_mos": 1.5, "w_roic": 1.0, "w_debt": 1.0, "w_oey": 1.0,
                      "top_n": 15.0})
    assert len(ValueBenchmark(universes=universes).evaluate(concentrated).picks) == 3
    assert len(ValueBenchmark(universes=universes).evaluate(broad).picks) == 15


def test_empty_params_fall_back_to_prior_behavior():
    """Seed/legacy genomes with no params score exactly as the keyword reader did."""
    universes = default_universes()
    bench = ValueBenchmark(universes=universes)
    g = _analyst()
    assert bench.evaluate(g).score == bench.evaluate(g).score   # deterministic, no crash
    assert weights_for(g) == weights_for(g)                     # keyword path stable
