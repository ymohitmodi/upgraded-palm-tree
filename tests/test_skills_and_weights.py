from __future__ import annotations

from pathlib import Path

from nyx.agents.base import Genome
from nyx.domains.investing.backtest import llm_factor_weights
from nyx.memory import MemoryStore
from nyx.skills import sync_skills

REPO_SKILLS = Path(__file__).resolve().parent.parent / "nyx" / "skill_packs"


def test_shipped_skill_packs_exist_and_are_deep():
    for name in ("value-investing-buffett-graham.md", "eb1a-ai-security-engineer.md",
                 "frontier-model-engineering.md"):
        p = REPO_SKILLS / name
        assert p.exists(), f"missing skill pack: {name}"
        assert len(p.read_text(encoding="utf-8")) > 3000  # in-depth, not a stub


def test_skills_ingest_per_section(tmp_path):
    """A multi-section skill file becomes one long-term lesson per ## section."""
    d = tmp_path / "skills"
    d.mkdir()
    (d / "playbook.md").write_text(
        "# Big Playbook\nIntro para long enough to keep.\n\n"
        "## Section One\nDeep content one that is clearly long enough to be retained here.\n\n"
        "## Section Two\nDeep content two that is also long enough to be retained here.\n")
    store = MemoryStore(tmp_path / "m.jsonl")
    n = sync_skills(store, d)
    assert n == 3  # preamble + 2 sections
    assert all(le.kind == "skill" and le.tier == "long_term" for le in store.all())
    hits = store.recall("tell me about section two content")
    assert hits and "Section Two" in hits[0].text


def test_real_buffett_pack_ingests_many_sections(tmp_path):
    store = MemoryStore(tmp_path / "m.jsonl")
    n = sync_skills(store, REPO_SKILLS)
    assert n >= 20  # three deep packs, many sections each
    hits = store.recall("how do I compute owner earnings and margin of safety")
    assert hits and hits[0].kind == "skill"


def test_llm_factor_weights_uses_model_not_regex(monkeypatch):
    """When live, weights come from the model's rating — no substring counting."""
    class Cfg:
        mock_mode = False
        def model(self, role):  # noqa: D102
            return "x"

    class FakeProvider:
        name = "fake"
        def chat(self, model, messages, **kw):
            from nyx.providers.base import Completion
            # Charter says nothing about factors, yet the model rates them.
            return Completion(text="3,0,1,2", model=model)

    g = Genome(role="analyst", system_prompt="Be a great investor.")
    w = llm_factor_weights(g, Cfg(), FakeProvider())
    assert w == {"mos": 3.0, "roic": 0.0, "debt": 1.0, "oey": 2.0}


def test_llm_factor_weights_falls_back_offline():
    class Cfg:
        mock_mode = True
        def model(self, role):  # noqa: D102
            return "x"

    g = Genome(role="analyst", system_prompt="margin of safety and roic")
    w = llm_factor_weights(g, Cfg(), None)          # mock → deterministic reader
    assert w["mos"] > 0 and w["roic"] > 0
