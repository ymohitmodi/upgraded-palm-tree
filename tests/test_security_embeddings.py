from __future__ import annotations

import pytest

from nyx.embeddings import HashingEmbedder, cosine
from nyx.memory import MemoryStore
from nyx.security.egress import EgressBlocked, check_url
from nyx.tools.registry import ToolRegistry, ToolResult


# -- embeddings-based recall -------------------------------------------------
def test_hashing_embedder_is_deterministic_and_normalized():
    e = HashingEmbedder(dim=256)
    v1, v2 = e.embed("margin of safety"), e.embed("margin of safety")
    assert v1 == v2
    assert abs(sum(x * x for x in v1) ** 0.5 - 1.0) < 1e-9  # unit length
    assert cosine(e.embed("owner earnings yield"),
                  e.embed("owner earnings")) > cosine(e.embed("owner earnings"),
                                                      e.embed("sourdough bread"))


def test_recall_is_semantic_not_just_keyword(tmp_path):
    store = MemoryStore(tmp_path / "m.jsonl")
    store.remember("Compute owner earnings and demand a margin of safety versus intrinsic value.",
                   tags=["investing"])
    store.remember("Proof sourdough overnight and bake at high heat for a crisp crust.",
                   tags=["baking"])
    # Query shares few exact tokens with the investing lesson but is closer in space.
    hits = store.recall("discount to intrinsic worth when valuing a cheap business")
    assert hits and "margin of safety" in hits[0].text


def test_recall_falls_back_when_embedder_fails(tmp_path):
    class BrokenEmbedder:
        dim = 8
        def embed(self, text):
            raise RuntimeError("no embeddings here")

    store = MemoryStore(tmp_path / "m.jsonl", embedder=BrokenEmbedder())
    store.remember("Validate inputs before shipping", tags=["security"])
    hits = store.recall("how do I validate inputs")   # keyword fallback still works
    assert hits and "Validate inputs" in hits[0].text


# -- SSRF / egress guard -----------------------------------------------------
def test_egress_blocks_metadata_and_private_and_scheme():
    with pytest.raises(EgressBlocked):
        check_url("http://169.254.169.254/latest/meta-data/", resolve=False)
    with pytest.raises(EgressBlocked):
        check_url("http://127.0.0.1:8080/admin", resolve=False)
    with pytest.raises(EgressBlocked):
        check_url("http://10.0.0.5/internal", resolve=False)
    with pytest.raises(EgressBlocked):
        check_url("file:///etc/passwd", resolve=False)


def test_egress_allows_public_and_enforces_allowlist():
    check_url("https://www.sec.gov/data", allowed_domains=("sec.gov",), resolve=False)  # ok
    with pytest.raises(EgressBlocked):
        check_url("https://evil.example.com", allowed_domains=("sec.gov",), resolve=False)


# -- least-privilege tools ---------------------------------------------------
def test_tool_allowlist_denies_unpermitted_tools():
    reg = ToolRegistry()
    reg.add("web_fetch", "fetch", lambda url: ToolResult(ok=True, data=url))
    reg.add("edgar_facts", "sec", lambda ticker: ToolResult(ok=True, data=ticker))
    reg.set_allowed({"web_fetch"})
    assert reg.call("web_fetch", url="x").ok
    denied = reg.call("edgar_facts", ticker="AAPL")
    assert not denied.ok and "not permitted" in denied.error
    reg.set_allowed(None)                       # None restores full access
    assert reg.call("edgar_facts", ticker="AAPL").ok
