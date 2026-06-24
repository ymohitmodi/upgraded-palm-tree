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
