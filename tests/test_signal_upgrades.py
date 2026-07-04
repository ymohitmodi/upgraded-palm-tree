"""The three 'make the signal real' upgrades: executed fitness, real embeddings,
outer feedback loop."""
from __future__ import annotations

from nyx.capabilities import CapabilityRunner, select_for
from nyx.embeddings import HashingEmbedder, ProviderEmbedder, embedder_for
from nyx.memory import MemoryStore
from nyx.providers.mock import MockProvider


def _cfg(tmp_path):
    from nyx.config import load_config

    cfg = load_config(dotenv=False)
    cfg.ledger_path = str(tmp_path / "l.jsonl")
    cfg.memory_path = str(tmp_path / "mem.jsonl")
    cfg.evolution_archive = str(tmp_path / "arch.jsonl")
    cfg.web_cache_dir = str(tmp_path / "wc")
    cfg.autonomy = "autonomous"
    return cfg


# -- #1 evolution optimizes EXECUTED correctness ----------------------------
def test_coder_fitness_is_executed_not_keywords(config, constitution_path):
    from nyx.constitution import Constitution
    from nyx.evolution.engine import EvolutionEngine

    const = Constitution.load(constitution_path, mode=config.constitution_mode)
    eng = EvolutionEngine(config=config, provider=MockProvider(config), constitution=const,
                          role="coder")
    # The coder seed's score equals the executed SWE-bench pass fraction (0.85 wt)
    # plus a small genome term — i.e. it reflects real execution, and the mock
    # coder passes 2/4 tasks.
    seed = eng._seed_genome()
    score = eng.benchmark(eng._agent_for(seed))
    assert 0.4 < score < 0.7          # dominated by executed 0.5 pass-rate, not keywords


# -- #2 real (provider) embeddings ------------------------------------------
def test_provider_embedder_powers_recall():
    emb = ProviderEmbedder(MockProvider(), model="nomic-embed-text")
    v = emb.embed("margin of safety")
    assert isinstance(v, list) and len(v) == 256


def test_embedder_selector_prefers_provider_when_live():
    class Cfg:
        mock_mode = False
        model_embed = "nomic-embed-text"

    assert isinstance(embedder_for(Cfg(), MockProvider()), ProviderEmbedder)

    class MockCfg:
        mock_mode = True
        model_embed = "x"

    assert isinstance(embedder_for(MockCfg(), MockProvider()), HashingEmbedder)


def test_recall_works_with_provider_embedder(tmp_path):
    store = MemoryStore(tmp_path / "m.jsonl",
                        embedder=ProviderEmbedder(MockProvider(), "nomic-embed-text"))
    store.remember("Owner earnings are the cash a business can distribute.", tags=["investing"])
    store.remember("Sourdough needs a long cold ferment.", tags=["baking"])
    hits = store.recall("distributable cash from a business")
    assert hits and "Owner earnings" in hits[0].text


# -- #3 outer feedback loop: realized outcomes become a track record ---------
def test_investing_run_accumulates_track_record(tmp_path):
    cap = select_for("find deep-value undervalued companies to invest in")
    runner = CapabilityRunner(cap, config=_cfg(tmp_path))
    runner.run("find deep-value undervalued companies", max_cycles=3,
               evolve_every=0, refresh_every=0)
    records = [x for x in runner.memory.all() if x.kind == "track-record"]
    assert records                              # realized returns recorded
    assert any("realized risk-adjusted return" in r.text for r in records)
    assert all(r.trusted for r in records)      # internal outcome, trusted


def test_software_shipped_records_verified_track_record(tmp_path):
    from nyx.capabilities.software import SoftwareFactoryCapability

    runner = CapabilityRunner(SoftwareFactoryCapability(), config=_cfg(tmp_path))
    runner.run("build a small feature", max_cycles=1, evolve_every=0, refresh_every=0)
    records = [x for x in runner.memory.all() if x.kind == "track-record"]
    assert any("execution-verified" in r.text for r in records)
