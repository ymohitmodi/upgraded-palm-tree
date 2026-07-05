"""Context broker: goal-driven discovery + hygiene (no pollution)."""
from __future__ import annotations

from nyx.context_broker import ContextBroker
from nyx.memory import MemoryStore


def test_multi_probe_discovers_context_across_subgoals(tmp_path):
    store = MemoryStore(tmp_path / "m.jsonl")
    store.remember("For billing features, validate currency precision and rounding.",
                   tags=["billing"])
    store.remember("Retention beats acquisition: fix churn before scaling marketing.",
                   tags=["retention"])
    store.remember("Sourdough needs a long cold ferment.", tags=["baking"])
    # A compound goal: a single query might miss one sub-topic; the broker probes both.
    bundle = ContextBroker().assemble(
        "Build a billing dashboard and improve customer retention", store)
    joined = " ".join(bundle.lessons).lower()
    assert "billing" in joined or "currency" in joined
    assert "retention" in joined or "churn" in joined
    assert "sourdough" not in joined                 # irrelevant context excluded


def test_relevance_floor_drops_weak_matches(tmp_path):
    store = MemoryStore(tmp_path / "m.jsonl")
    store.remember("Margin of safety protects against permanent capital loss.", tags=["investing"])
    store.remember("Kubernetes ingress controllers route external traffic.", tags=["devops"])
    bundle = ContextBroker(min_relevance=0.05).assemble(
        "what margin of safety should I demand for a cheap stock", store)
    assert bundle.lessons and "margin of safety" in bundle.lessons[0].lower()
    assert not any("kubernetes" in x.lower() for x in bundle.lessons)


def test_budget_and_dedup_keep_context_lean(tmp_path):
    store = MemoryStore(tmp_path / "m.jsonl")
    # Many near-duplicate high-relevance lessons.
    for i in range(12):
        store.remember(f"Validate all inputs before processing. Case {i}. " + "x" * 200,
                       tags=["security", "validation"])
    bundle = ContextBroker(budget_chars=600, max_items=6).assemble(
        "how should I validate inputs", store)
    assert 1 <= len(bundle.lessons) <= 6
    assert bundle.chars <= 600 + 250          # respects the budget (last item may straddle)
    assert bundle.dropped >= 1                # low-signal extras were pruned


def test_trivial_low_signal_items_are_dropped(tmp_path):
    store = MemoryStore(tmp_path / "m.jsonl")
    store.remember("ok", tags=["misc"])                       # trivially short
    store.remember("Prefer recurring revenue: MRR compounds where one-off sales reset.",
                   tags=["pricing"])
    bundle = ContextBroker(min_len=20).assemble("how should I price for recurring revenue", store)
    assert all(len(x) >= 20 for x in bundle.lessons)          # no trivial snippet injected
    assert any("mrr" in x.lower() or "recurring" in x.lower() for x in bundle.lessons)


def test_empty_memory_yields_empty_bundle(tmp_path):
    bundle = ContextBroker().assemble("anything", MemoryStore(tmp_path / "m.jsonl"))
    assert bundle.lessons == [] and bundle.chars == 0
