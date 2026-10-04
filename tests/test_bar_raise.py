"""Bar-raise batch: MCP server factory, all-letters range, cross-capability
doctrine recall, and the moat-aware assessment parse."""
from __future__ import annotations

from nyx.domains.investing.assess import assess_company
from nyx.domains.investing.buffett import letter_urls
from nyx.memory import MemoryStore
from nyx.tools.mcp import MCP_CATALOG, build_manifest, load_manifest, write_manifest


# -- MCP factory ---------------------------------------------------------------
def test_mcp_factory_builds_multiple_servers():
    m = build_manifest(["edgartools", "paper-search", "web-researcher", "hexstrike-ai"],
                       identity="Jane Doe j@x.com", python_exe="/py")
    servers = m["mcpServers"]
    assert set(servers) == {"edgartools", "paper-search", "web-researcher", "hexstrike-ai"}
    assert servers["edgartools"]["env"]["EDGAR_IDENTITY"] == "Jane Doe j@x.com"
    assert servers["paper-search"]["command"] == "uvx"
    assert servers["web-researcher"]["command"] == "npx"
    assert servers["hexstrike-ai"]["command"] == "/py"        # {python} filled


def test_mcp_factory_ignores_unknown_and_all_catalog_entries_valid():
    m = build_manifest(["edgartools", "does-not-exist"], python_exe="/py")
    assert set(m["mcpServers"]) == {"edgartools"}             # typo can't add a bad server
    for spec in MCP_CATALOG.values():
        assert spec["command"] and "note" in spec            # catalog is well-formed


def test_write_manifest_merges_additively(tmp_path):
    path = tmp_path / "mcp.json"
    write_manifest(path, ["edgartools"], python_exe="/py")
    write_manifest(path, ["paper-search"], python_exe="/py")   # --add is additive
    names = {s.name for s in load_manifest(path)}
    assert names == {"edgartools", "paper-search"}


# -- all Buffett letters -------------------------------------------------------
def test_letter_urls_span_the_full_history():
    urls = letter_urls(1977, 2025)
    assert len(urls) == 49 and urls[0][0] == 1977 and urls[-1][0] == 2025
    assert urls[0][1].endswith("1977.html")                   # old letters are html
    assert urls[-1][1].endswith("2025ltr.pdf")                # recent are pdf


# -- cross-capability doctrine recall ------------------------------------------
def test_recall_doctrine_federates_trusted_principles(tmp_path):
    invest = MemoryStore(tmp_path / "memory-value-investing.jsonl")
    advisor = MemoryStore(tmp_path / "memory-advisor.jsonl")
    p = invest.remember("Favor durable moats that compound owner-earnings for years.",
                        kind="principle", tags=["moat", "compounding"], source="buffett",
                        weight=3.0, trusted=True)
    p.tier = "long_term"
    n = advisor.remember("Ground every research claim in a citable source.",
                         kind="principle", tags=["research", "rigor"], source="career",
                         weight=3.0, trusted=True)
    n.tier = "long_term"
    invest._flush()
    advisor._flush()

    # Investor recall alone: no advisor doctrine.
    assert not any("citable" in x.text for x in invest.recall("research rigor citation", k=5))
    # Federated: the advisor's principle surfaces for the investor.
    invest.attach_doctrine(advisor)
    fed = invest.recall_doctrine("research rigor grounded citation", k=4)
    assert any("citable" in x.text for x in fed)
    # Untrusted/short-term never crosses over.
    advisor.remember("random untrusted note about citations", kind="research",
                     tags=["research"], trusted=False)
    advisor._flush()
    assert all(x.trusted and x.tier == "long_term" for x in
               invest.recall_doctrine("citation", k=4))


# -- moat-aware assessment parsing (offline stays neutral) ---------------------
def test_assess_offline_neutral_and_moat_field_optional():
    a = assess_company(None, None, ticker="KO", factor_score=1.0, metrics="m",
                       principles="p", evidence="e")
    assert a.llm_score == 5.0 and "offline" in a.rationale
