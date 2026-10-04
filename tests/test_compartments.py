"""Compartmentalization: host-partitioned web cache, per-capability memory,
and readable (non-JSON) memory formation."""
from __future__ import annotations

import hashlib
import json

from nyx.domains.investing.filings import readable
from nyx.tools.web import WebFetcher


def _transport(body: bytes = b"<html><p>hello</p></html>"):
    def transport(url, headers):
        return 200, body, url
    return transport


# -- web cache ----------------------------------------------------------------
def test_cache_is_partitioned_by_host(tmp_path):
    fetcher = WebFetcher(cache_dir=tmp_path, transport=_transport())
    fetcher.fetch("https://www.sec.gov/some/filing")
    fetcher.fetch("https://finance.yahoo.com/chart/AAPL")
    assert (tmp_path / "www.sec.gov").is_dir()
    assert (tmp_path / "finance.yahoo.com").is_dir()
    assert not list(tmp_path.glob("*.json"))            # nothing lands in the flat root


def test_cache_reads_legacy_flat_layout(tmp_path):
    """Entries cached before partitioning must stay warm (no mass re-fetch)."""
    url = "https://www.sec.gov/legacy/doc"
    h = hashlib.sha256(url.encode()).hexdigest()[:20]
    (tmp_path / f"{h}.json").write_text(
        json.dumps({"url": url, "status": 200, "text": "legacy cached body"}),
        encoding="utf-8")

    def explode(u, headers):  # network must NOT be touched
        raise AssertionError("legacy cache should have served this")

    doc = WebFetcher(cache_dir=tmp_path, transport=explode).fetch(url)
    assert doc.from_cache and doc.text == "legacy cached body"


# -- memory formation ----------------------------------------------------------
def test_readable_flattens_mcp_json_payloads():
    payload = json.dumps({"success": True, "data": {
        "company": "Apple Inc.", "form": "10-K", "total_notes": 16,
        "notes": [{"number": 9, "title": "Debt", "expands": ["Term debt"]}],
        "empty": "", "nothing": None,
    }})
    text = readable(payload)
    assert "{" not in text and '"' not in text          # no wire format survives
    assert "company: Apple Inc." in text
    assert "notes.title: Debt" in text
    assert "empty" not in text and "nothing" not in text  # empties dropped


def test_readable_passes_through_non_json_and_respects_limit():
    prose = "Plain narrative text from a filing." * 20
    assert readable(prose, limit=50) == prose[:50]
    assert readable("not json at all") == "not json at all"


# -- per-capability memory ------------------------------------------------------
def test_runner_compartmentalizes_memory_per_capability(tmp_path):
    from nyx.capabilities import CapabilityRunner
    from nyx.capabilities.advisor import AdvisorCapability
    from nyx.config import load_config

    cfg = load_config(dotenv=False)
    cfg.ollama_api_key = ""
    cfg.ledger_path = str(tmp_path / "l.jsonl")
    cfg.memory_path = str(tmp_path / "memory.jsonl")
    cfg.evolution_archive = str(tmp_path / "arch.jsonl")
    cfg.memory_per_capability = True

    runner = CapabilityRunner(AdvisorCapability(), config=cfg)
    assert str(runner.memory.path).endswith("memory-advisor.jsonl")

    cfg.memory_per_capability = False
    runner2 = CapabilityRunner(AdvisorCapability(), config=cfg)
    assert str(runner2.memory.path).endswith("memory.jsonl")   # default unchanged
