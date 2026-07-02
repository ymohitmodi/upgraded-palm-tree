"""Tests for LLM routing, the advisor capability, scalable crawl, and skills."""
from __future__ import annotations

from nyx.capabilities import CapabilityRunner, select_for
from nyx.capabilities.router import route
from nyx.memory import MemoryStore
from nyx.skills import sync_skills
from nyx.tools.web import WebFetcher


def _cfg(tmp_path):
    from nyx.config import load_config

    cfg = load_config(dotenv=False)
    cfg.ledger_path = str(tmp_path / "l.jsonl")
    cfg.memory_path = str(tmp_path / "mem.jsonl")
    cfg.evolution_archive = str(tmp_path / "arch.jsonl")
    cfg.web_cache_dir = str(tmp_path / "wc")
    cfg.autonomy = "autonomous"
    return cfg


def test_router_falls_back_deterministically_in_mock(tmp_path):
    cfg = _cfg(tmp_path)
    from nyx.providers.mock import MockProvider

    assert route("grow my senior SDE career and prep EB-1 publications",
                 cfg, MockProvider(cfg)).name == "advisor"
    assert route("find undervalued stocks", cfg, MockProvider(cfg)).name == "value-investing"
    assert route("build a todo app", cfg, MockProvider(cfg)).name == "software"


def test_router_uses_llm_when_live(tmp_path):
    """A live provider's answer routes semantically — no keyword rules involved."""
    cfg = _cfg(tmp_path)
    cfg.ollama_api_key = "test-key"  # makes mock_mode False → LLM routing path
    assert not cfg.mock_mode

    class FakeLive:
        name = "fake"
        def chat(self, model, messages, **kw):
            from nyx.providers.base import Completion
            assert "OBJECTIVE" in messages[-1].content
            return Completion(text="value-investing\n", model=model)

    # Objective has NO investing keywords — only the LLM can route it.
    cap = route("help me compound my savings safely", cfg, FakeLive())
    assert cap.name == "value-investing"


def test_advisor_capability_runs_ambiguous_goal(tmp_path):
    cap = select_for("grow my career toward senior staff and EB-1 readiness")
    assert cap.name == "advisor"
    runner = CapabilityRunner(cap, config=_cfg(tmp_path))
    report = runner.run("grow my career toward senior staff and EB-1 readiness",
                        max_cycles=3, evolve_every=0, refresh_every=0)
    assert len(report.cycles) >= 1
    assert all(c.ok for c in report.cycles)          # gated deliverables passed
    assert report.long_term_lessons >= 10            # career/EB-1 doctrine seeded
    assert report.ledger_ok


def test_crawl_fetches_concurrently_and_survives_failures(tmp_path):
    def transport(url, headers):
        if "bad" in url:
            raise RuntimeError("boom")
        return 200, f"<p>page {url[-1]}</p>".encode(), url

    f = WebFetcher(cache_dir=tmp_path / "wc", rate_limit_seconds=0, transport=transport)
    docs = f.crawl([f"https://a.test/{i}" for i in range(5)] + ["https://bad.test/x"])
    assert sum(1 for d in docs if d.status == 200) == 5
    assert sum(1 for d in docs if d.status == 0) == 1  # failure contained


def test_skills_sync_into_long_term_memory(tmp_path):
    skills = tmp_path / "skills"
    skills.mkdir()
    (skills / "cold-outreach.md").write_text(
        "# Cold outreach playbook\nPersonalize the first line; one clear ask.")
    (skills / "seo-basics.md").write_text("# SEO basics\nOne intent per page.")
    store = MemoryStore(tmp_path / "m.jsonl")
    assert sync_skills(store, skills) == 2
    assert store.stats()["long_term"] == 2
    hits = store.recall("how do I do cold outreach to customers")
    assert hits and hits[0].kind == "skill"
    assert sync_skills(store, skills) == 2  # idempotent: reinforces, no dupes
    assert len(store) == 2
