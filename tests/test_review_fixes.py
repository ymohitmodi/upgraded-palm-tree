"""Regression tests for the code-review findings + solopreneur doctrine."""
from __future__ import annotations

from nyx.memory import MemoryStore
from nyx.tools.web import WebFetcher


def test_web_fetcher_does_not_cache_errors(tmp_path):
    """Finding: a transient 503 must not poison the cache forever."""
    calls = {"n": 0}

    def transport(url, headers):
        calls["n"] += 1
        return (503, b"oops", url) if calls["n"] == 1 else (200, b"fine", url)

    f = WebFetcher(cache_dir=tmp_path / "wc", rate_limit_seconds=0, transport=transport)
    assert f.fetch("https://x.test/a").status == 503
    d2 = f.fetch("https://x.test/a")     # retries instead of replaying the 503
    assert d2.status == 200 and not d2.from_cache
    assert f.fetch("https://x.test/a").from_cache  # success IS cached


def test_consolidate_no_double_count_multi_tag(tmp_path):
    """Finding: a lesson with two theme tags must join at most one principle."""
    store = MemoryStore(tmp_path / "m.jsonl")
    for i in range(3):
        store.remember(f"sec lesson {i}", tags=["sec", "fundamentals"])
    stats = store.consolidate(cluster_min=3)
    assert stats["consolidated"] == 1  # was 2 (duplicate principles) before the fix


def test_consolidate_fades_instead_of_deleting(tmp_path):
    """Finding: absorbed lessons fade (recallable, decayable) — not hard-deleted."""
    store = MemoryStore(tmp_path / "m.jsonl")
    for i in range(3):
        store.remember(f"decision record {i}", tags=["decision"], kind="pattern")
    store.consolidate(cluster_min=3)
    kinds = {le.kind for le in store.all()}
    assert "principle" in kinds and "pattern" in kinds  # records survive


def test_registry_builtins_survive_early_custom_registration():
    """Finding: register(custom) before select_for must not suppress built-ins."""
    from nyx.capabilities import registry as reg
    from nyx.capabilities.base import Capability, CycleResult

    class Custom(Capability):
        name = "custom-test"
        def matches(self, objective):  # noqa: D102
            return "custom-test" in objective
        def execute(self, task, ctx):  # noqa: D102
            return CycleResult(item=task)

    reg._REGISTRY.clear()
    reg.register(Custom)
    assert reg.select_for("build a web app").name == "software"
    assert reg.select_for("undervalued stocks").name == "value-investing"
    assert reg.select_for("do the custom-test thing").name == "custom-test"
    reg._REGISTRY.clear()  # leave a clean slate


def test_registry_returns_fresh_instances():
    """Finding: singleton capability state must not leak across selections."""
    from nyx.capabilities import select_for

    a = select_for("undervalued stocks")
    b = select_for("undervalued stocks")
    assert a is not b


def test_keyword_stuffing_saturates():
    """Finding: repeating a doctrine keyword must not keep raising fitness weight."""
    from nyx.agents.base import Genome
    from nyx.domains.investing.backtest import genome_factor_weights

    once = genome_factor_weights(Genome(role="analyst", system_prompt="margin of safety"))
    spam = genome_factor_weights(Genome(role="analyst", system_prompt="margin of safety " * 40))
    # Saturates at the cap (3 mentions); further repetition adds no weight.
    assert spam["mos"] == genome_factor_weights(
        Genome(role="analyst", system_prompt="margin of safety " * 3))["mos"]
    assert spam["mos"] <= once["mos"] * 3


def test_compaction_respects_budget_and_line_boundaries(config, constitution_path):
    from nyx.constitution import Constitution
    from nyx.factory.orchestrator import Factory
    from nyx.providers.mock import MockProvider

    config.context_char_budget = 600
    const = Constitution.load(constitution_path, mode=config.constitution_mode)
    factory = Factory(config=config, provider=MockProvider(config), constitution=const)
    text = "\n".join(f"line {i} with some content here" for i in range(200))
    out = factory._compact_context(text)
    assert len(out) <= 600  # hard budget, no +200 overrun
    head = out.split("…", 1)[0]
    assert head.rstrip("\n").endswith("here")  # cut on a line boundary


def test_solopreneur_doctrine_seeds_and_recalls(tmp_path):
    from nyx.domains.solopreneur import PRINCIPLES, seed_principles

    store = MemoryStore(tmp_path / "m.jsonl")
    n = seed_principles(store)
    assert n == len(PRINCIPLES)
    assert store.stats()["long_term"] == n
    hits = store.recall("how should I plan marketing and distribution for launch")
    assert hits and "distribution" in (hits[0].text + " ".join(hits[0].tags)).lower()


def test_software_capability_seeds_solopreneur_doctrine(tmp_path):
    from nyx.capabilities.software import SoftwareFactoryCapability

    store = MemoryStore(tmp_path / "m.jsonl")
    n = SoftwareFactoryCapability().seed_memory(store)
    assert n >= 10 and store.stats()["long_term"] >= 10
