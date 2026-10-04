from __future__ import annotations

from nyx.constitution import Constitution
from nyx.factory.orchestrator import Factory
from nyx.memory import MemoryStore, reflect_on_run
from nyx.providers.mock import MockProvider


def test_remember_recall_and_reinforce(tmp_path):
    store = MemoryStore(tmp_path / "mem.jsonl")
    store.remember("Validate currency precision for billing features", tags=["billing"])
    store.remember("Validate currency precision for billing features", tags=["billing"])  # dup
    assert len(store) == 1  # deduped
    only = store.all()[0]
    assert only.weight > 1.0  # reinforced

    store.remember("Use blue-green deploys for zero downtime", tags=["deploy"])
    hits = store.recall("how should I handle billing precision", k=3)
    assert hits and "billing" in hits[0].text.lower()


def test_recall_is_persistent(tmp_path):
    path = tmp_path / "mem.jsonl"
    MemoryStore(path).remember("Always validate inputs", tags=["security"])
    reloaded = MemoryStore(path)
    assert len(reloaded) == 1


def _factory(tmp_path, constitution_path, memory):
    from nyx.config import load_config

    cfg = load_config(dotenv=False)
    cfg.ledger_path = str(tmp_path / "l.jsonl")
    cfg.autonomy = "autonomous"
    const = Constitution.load(constitution_path, mode=cfg.constitution_mode)
    return Factory(config=cfg, provider=MockProvider(cfg), constitution=const, memory=memory)


def test_factory_reflects_and_recalls(tmp_path, constitution_path):
    memory = MemoryStore(tmp_path / "mem.jsonl")
    # First run: nothing to recall, but it reflects and stores a pattern.
    r1 = _factory(tmp_path, constitution_path, memory).build("Add a billing dashboard")
    assert r1.lessons_applied == 0
    assert len(memory) >= 1

    # Second, similar run: lessons are recalled and applied to the agents.
    r2 = _factory(tmp_path, constitution_path, memory).build("Add a billing exports page")
    assert r2.lessons_applied >= 1


def test_consolidation_abstracts_recurring_theme_into_long_term(tmp_path):
    store = MemoryStore(tmp_path / "mem.jsonl")
    # Three distinct short-term lessons sharing the 'billing' theme.
    for i in range(3):
        store.remember(f"For billing case {i}, satisfy G_SECURITY early", tags=["billing", "G_SECURITY"])
    assert store.stats()["long_term"] == 0

    stats = store.consolidate(cluster_min=3)
    assert stats["consolidated"] >= 1
    lt = [x for x in store.all() if x.tier == "long_term"]
    assert lt and lt[0].kind == "principle"
    assert "billing" in lt[0].text.lower()
    # The specifics were absorbed into the principle.
    assert store.stats()["long_term"] >= 1


def test_consolidation_decays_and_forgets_stale_lessons(tmp_path):
    store = MemoryStore(tmp_path / "mem.jsonl")
    lesson = store.remember("A one-off note unlikely to recur", tags=["misc"])
    # Simulate it being old and unused: push last_used far into the past.
    lesson.last_used = lesson.last_used - 60 * 86400  # 60 days ago
    stats = store.consolidate(half_life_days=7, min_weight=0.2, cluster_min=99)
    assert stats["forgotten"] >= 1
    assert len(store) == 0  # decayed below the floor and forgotten


def test_high_use_lesson_is_promoted_to_long_term(tmp_path):
    store = MemoryStore(tmp_path / "mem.jsonl")
    store.remember("Validate inputs", tags=["security"])
    for _ in range(3):
        store.recall("how to validate inputs")  # bumps uses
    stats = store.consolidate(cluster_min=99, promote_uses=3)
    assert stats["promoted"] >= 1


def test_context_compaction_bounds_working_memory(config, constitution_path):
    from nyx.factory.orchestrator import Factory
    from nyx.providers.mock import MockProvider

    config.context_char_budget = 500
    const = Constitution.load(constitution_path, mode=config.constitution_mode)
    factory = Factory(config=config, provider=MockProvider(config), constitution=const)
    big = "must validate\n" + ("x" * 5000) + "\nsecurity gate"
    out = factory._compact_context(big)
    assert len(out) <= config.context_char_budget + 200
    assert "compacted" in out
    # Salient lines are preserved.
    assert "validate" in out


def test_reflect_on_blocked_run_records_lesson(tmp_path, constitution_path):
    """A blocked gate should become a durable guardrail lesson."""
    memory = MemoryStore(tmp_path / "mem.jsonl")

    class _Blocked:
        intent = "Risky feature"
        shipped = False
        findings = ["injection_blocked from ticket"]

        class _S:
            stage = "review"
            gate = "G_SECURITY"
            passed = False
            rationale = "stage=review gate=G_SECURITY -> BLOCK: G_SECURITY: secrets"
            claims: dict = {}

        stages = [_S()]

    learned = reflect_on_run(_Blocked(), memory)
    assert any(ln.kind == "lesson" for ln in learned)
    assert any(ln.kind == "risk" for ln in learned)
    assert len(memory) >= 2
