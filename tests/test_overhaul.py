"""Overhaul regressions: negation-aware forbidden scan, robust advisor planning,
radar-first backlogs, and the long-run wall-clock budget."""
from __future__ import annotations

from nyx.capabilities.advisor import RADAR_TASK, AdvisorCapability
from nyx.constitution import Constitution

CONST = "constitution/constitution.yaml"


# -- negation-aware forbidden scan ---------------------------------------------
def test_restating_a_rule_is_not_a_violation():
    """'Never fabricate results' is the RULE, not a breach — the EB-1A objective
    itself contains this phrase and was false-blocked at G_SECURITY."""
    c = Constitution.load(CONST)
    assert c.check_forbidden(
        "Ground every claim; never fabricate citations, credentials, or results.") == []
    assert c.check_forbidden(
        "Do not present fabricated test results as verified.") == []
    assert c.check_forbidden("We avoid made-up numbers and financial figures.") == []


def test_actual_violations_still_block():
    c = Constitution.load(CONST)
    assert c.check_forbidden("I fabricated the test results to make them pass.")
    assert c.check_forbidden("Just pretend the tests pass and ship it.")
    # A negated mention earlier must not mask a real violation later.
    both = ("Never fabricate results.\n"
            "However, here we faked the test results to save time.")
    assert c.check_forbidden(both)


# -- advisor planning -----------------------------------------------------------
def test_backlog_parser_accepts_bullets_numbers_and_parens():
    text = ("Here is the plan:\n"
            "- Inventory the evidence for each criterion\n"
            "2. Draft the judging outreach emails\n"
            "(3) Build the publication pipeline tracker\n"
            "* Refine the remuneration evidence file\n"
            "ok\n")   # short junk line ignored
    items = AdvisorCapability._parse_backlog(text)
    assert len(items) == 4
    assert items[0].startswith("Inventory") and items[2].startswith("Build")


def test_fallback_backlog_is_structured_not_milestones():
    cap = AdvisorCapability()
    items = cap._fallback_backlog("Build my EB-1A case")
    assert len(items) >= 4
    import re
    assert not any(re.search(r"—\s*milestone\s*\d", t) for t in items)  # old useless shape
    assert any("criterion" in t.lower() for t in items)


def test_plan_leads_with_research_radar(tmp_path):
    """Every plan starts with the radar (hot topics / white space / venues),
    and the offline fallback never degenerates into one amorphous task."""
    from nyx.capabilities import CapabilityRunner
    from nyx.config import load_config

    cfg = load_config(dotenv=False)
    cfg.ollama_api_key = ""
    cfg.ledger_path = str(tmp_path / "l.jsonl")
    cfg.memory_path = str(tmp_path / "m.jsonl")
    cfg.evolution_archive = str(tmp_path / "a.jsonl")

    cap = AdvisorCapability()
    runner = CapabilityRunner(cap, config=cfg)
    backlog = cap.plan("Build my EB-1A extraordinary-ability case", runner.context(0))
    assert backlog[0] == RADAR_TASK
    assert len(backlog) >= 4
    assert len(set(backlog)) == len(backlog)      # distinct tasks, no repeats


# -- long-run wall clock ----------------------------------------------------------
def test_hours_budget_stops_the_loop(tmp_path):
    from nyx.capabilities import CapabilityRunner
    from nyx.config import load_config

    cfg = load_config(dotenv=False)
    cfg.ollama_api_key = ""
    cfg.ledger_path = str(tmp_path / "l.jsonl")
    cfg.memory_path = str(tmp_path / "m.jsonl")
    cfg.evolution_archive = str(tmp_path / "a.jsonl")

    runner = CapabilityRunner(AdvisorCapability(), config=cfg)
    report = runner.run("grow my career", max_cycles=None, refresh_every=0,
                        evolve_every=0, hours=1e-9)      # deadline already passed
    assert len(report.cycles) == 0                        # loop never started a cycle
    entries = runner.ledger.read()
    assert any(e.action == "time_budget_reached" for e in entries)
