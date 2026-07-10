"""Advisor capability: research tools, deliverable rubric, evolution, dossier."""
from __future__ import annotations

from nyx.domains.career import ADVISOR_HELDOUT, ADVISOR_SUITE, AdvisorBenchmark, rubric_score
from nyx.tools.research import arxiv_url, parse_arxiv_atom

_ATOM = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title type="html">ArXiv Query Results</title>
  <entry>
    <id>http://arxiv.org/abs/2501.01234v1</id>
    <published>2025-01-03T18:00:00Z</published>
    <title>Cloud Vulnerability Scanning at Scale</title>
    <summary>We present a system for continuous scanning &amp; triage.</summary>
  </entry>
  <entry>
    <id>http://arxiv.org/abs/2501.05678v2</id>
    <published>2025-01-09T09:30:00Z</published>
    <title>SoK: Security of  Software
    Supply Chains</title>
    <summary>A systematization of knowledge.</summary>
  </entry>
</feed>"""


def test_parse_arxiv_atom_extracts_papers():
    papers = parse_arxiv_atom(_ATOM)
    assert len(papers) == 2
    assert papers[0].title == "Cloud Vulnerability Scanning at Scale"
    assert papers[0].url == "http://arxiv.org/abs/2501.01234v1"
    assert papers[0].published == "2025-01-03"
    assert "&" in papers[0].summary                      # entity decoded
    assert papers[1].title == "SoK: Security of Software Supply Chains"  # whitespace folded


def test_parse_arxiv_atom_is_resilient_and_bounded():
    assert parse_arxiv_atom("not xml") == []
    assert parse_arxiv_atom("") == []
    assert len(parse_arxiv_atom(_ATOM, limit=1)) == 1


def test_arxiv_url_ands_terms_and_bounds():
    url = arxiv_url("cloud security & scanning of things", limit=500)
    assert url.startswith("https://export.arxiv.org/api/query?search_query=all:")
    assert " " not in url
    # Substantive terms AND-ed; junk tokens ("&", "of") dropped.
    assert "all:cloud+AND+all:security+AND+all:scanning+AND+all:things" in url
    assert "max_results=50" in url                        # clamped
    assert "sortBy=relevance" in url


def test_arxiv_url_supports_or_recall_fallback():
    """Objective-derived queries (e.g. EB-1A phrasing) can AND-match nothing;
    the fetcher retries with OR so the radar never runs on zero evidence."""
    url = arxiv_url("extraordinary ability evidence", op="OR")
    assert "all:extraordinary+OR+all:ability+OR+all:evidence" in url


# -- deliverable rubric -------------------------------------------------------
_GOOD = """# Criterion: Judging others' work
- Evidence needed: program-committee invitations, review records.
- Source: https://sp2026.ieee-security.org/cfp — reviewer call open until 2026-09-01.
- Milestone: submit reviewer application by August 2026.
- Draft email attached below with 3 qualifications and 12 published reviews.
NEXT ACTION: email the artifact-evaluation chair today.
"""


def test_rubric_rewards_grounded_structured_deliverables():
    vague = ("You should generally try to become more visible in your field and "
             "look for opportunities to review papers when they come up sometime.")
    assert rubric_score(_GOOD) > rubric_score(vague)
    assert rubric_score("") == 0.0
    assert rubric_score("short") == 0.0


def test_rubric_saturates_and_penalizes_guarantees():
    stuffed = _GOOD + "https://x.test " * 50 + "2026 " * 50
    more_stuffed = _GOOD + "https://x.test " * 500 + "2026 " * 500
    # Beyond each component's cap, further repetition buys nothing.
    assert rubric_score(more_stuffed) == rubric_score(stuffed)
    assert rubric_score(stuffed) <= 1.0
    promised = _GOOD + "\nApproval is guaranteed."
    assert rubric_score(promised) < rubric_score(_GOOD)          # constitution-aligned penalty


def test_advisor_benchmark_scores_agents_and_suites_are_disjoint():
    class FakeAgent:
        def __init__(self, text):
            self._t = text

        def run(self, task):
            class R:
                text = self._t
            return R()

    good, bad = AdvisorBenchmark()(FakeAgent(_GOOD)), AdvisorBenchmark()(FakeAgent("meh"))
    assert good > bad >= 0.0
    assert not set(ADVISOR_SUITE) & set(ADVISOR_HELDOUT)   # eval not contaminated


# -- offline end-to-end: evolution runs, dossier is written --------------------
def test_advisor_runs_evolves_and_writes_dossier(tmp_path):
    from nyx.capabilities import CapabilityRunner
    from nyx.capabilities.advisor import AdvisorCapability
    from nyx.config import load_config

    cfg = load_config(dotenv=False)
    cfg.ollama_api_key = ""                        # force mock regardless of host env
    cfg.ledger_path = str(tmp_path / "l.jsonl")
    cfg.memory_path = str(tmp_path / "m.jsonl")
    cfg.evolution_archive = str(tmp_path / "arch.jsonl")
    cfg.web_cache_dir = str(tmp_path / "wc")
    cfg.autonomy = "autonomous"

    runner = CapabilityRunner(AdvisorCapability(), config=cfg)
    report = runner.run("Build my EB-1A extraordinary-ability case; keep refining",
                        max_cycles=2, evolve_every=2, generations=3, refresh_every=0)
    assert len(report.cycles) >= 1
    assert report.evolutions >= 1                  # evolution actually ran for the advisor
    assert report.genome_score_after is not None   # a genome was adopted from the archive
    assert all(c.score is not None for c in report.cycles)   # rubric-scored deliverables
    dossier = tmp_path / "dossier"
    files = list(dossier.glob("*.md")) if dossier.exists() else []
    assert files, "gated deliverables should be written to the living dossier"
    body = files[0].read_text(encoding="utf-8")
    assert body.startswith("# ") and "produced by the NYX advisor" in body
