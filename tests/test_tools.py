from __future__ import annotations

from nyx.memory import MemoryStore
from nyx.tools import WebFetcher, build_toolbox, html_to_text
from nyx.tools.mcp import load_manifest, write_sample_manifest
from nyx.tools.registry import ToolRegistry, ToolResult


def _fake_transport(body: bytes, status: int = 200):
    def transport(url, headers):
        assert "User-Agent" in headers  # politeness enforced
        return status, body, url
    return transport


def test_html_to_text_strips_markup_and_scripts():
    html = "<html><script>evil()</script><body><h1>Hi</h1><p>Value &amp; price</p></body></html>"
    text = html_to_text(html)
    assert "evil" not in text
    assert "Hi" in text and "Value & price" in text


def test_web_fetcher_caches_and_extracts_text(tmp_path):
    fetcher = WebFetcher(
        cache_dir=tmp_path / "wc", rate_limit_seconds=0,
        transport=_fake_transport(b"<p>hello <b>world</b></p>"),
    )
    d1 = fetcher.fetch("https://example.com/x")
    assert "hello world" in d1.text and not d1.from_cache
    d2 = fetcher.fetch("https://example.com/x")
    assert d2.from_cache  # served from disk cache


def test_web_fetcher_enforces_allowlist(tmp_path):
    fetcher = WebFetcher(
        cache_dir=tmp_path / "wc", rate_limit_seconds=0,
        allowed_domains=("sec.gov",), transport=_fake_transport(b"ok"),
    )
    assert fetcher.fetch("https://www.sec.gov/data").text == "ok"
    try:
        fetcher.fetch("https://evil.example.com/x")
        assert False, "should have blocked off-allowlist domain"
    except PermissionError:
        pass


def test_registry_audits_and_guardrails(tmp_path):
    from nyx.observability.ledger import AuditLedger

    ledger = AuditLedger(tmp_path / "l.jsonl")
    reg = ToolRegistry(ledger=ledger)
    reg.add("echo", "echo text", lambda text: ToolResult(ok=True, data=text), {"text": "in"})
    assert reg.call("echo", text="hi").data == "hi"
    assert not reg.call("nope").ok  # unknown tool
    # A tool that leaks a secret is blocked by guardrails.
    reg.add("leak", "leaks", lambda: ToolResult(ok=True, data="AKIA" + "1234567890ABCDEF"))
    assert not reg.call("leak").ok


def test_mcp_manifest_roundtrip(tmp_path):
    path = tmp_path / "mcp.json"
    write_sample_manifest(path, identity="Jane Doe jane@example.com")
    specs = load_manifest(path)
    assert len(specs) == 1
    assert specs[0].name == "edgar"
    assert specs[0].command == "python" and "edgar.ai" in specs[0].args[-1]
    assert specs[0].env["EDGAR_IDENTITY"] == "Jane Doe jane@example.com"


def test_build_toolbox_registers_expected_tools(config):
    box = build_toolbox(config)
    names = box.names()
    assert "web_fetch" in names
    assert "edgar_financials" in names and "edgar_facts" in names


def test_buffett_seed_into_long_term_memory(tmp_path):
    from nyx.domains.investing import PRINCIPLES, seed_principles

    store = MemoryStore(tmp_path / "mem.jsonl")
    n = seed_principles(store)
    assert n == len(PRINCIPLES)
    assert store.stats()["long_term"] == n
    hits = store.recall("what margin of safety should I require for a cheap company")
    assert hits and "margin of safety" in hits[0].text.lower()
