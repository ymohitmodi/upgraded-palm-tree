"""NYX tools — the agents' hands on the outside world."""
from __future__ import annotations

from ..config import Config
from ..observability.ledger import AuditLedger
from .edgar import register_edgar_tools
from .mcp import load_manifest, register_mcp_servers
from .registry import ArgSpec, Tool, ToolRegistry, ToolResult
from .web import Document, WebFetcher, html_to_text

_URL_RE = r"https?://[^\s]{1,2048}"


def build_toolbox(config: Config, ledger: AuditLedger | None = None, provider=None) -> ToolRegistry:
    """Assemble the default toolbox: web scraping + SEC EDGAR + MCP servers.

    Passing ``provider`` enables the LLM injection classifier on external tool
    outputs (it falls back to heuristics when absent)."""
    registry = ToolRegistry(ledger=ledger, config=config, provider=provider)

    fetcher = WebFetcher(
        cache_dir=config.web_cache_dir,
        user_agent=config.user_agent,
        allowed_domains=config.allowed_domains,
        rate_limit_seconds=config.web_rate_limit_seconds,
    )
    registry.add(
        "web_fetch",
        "Fetch a URL and return readable text (cached, rate-limited, allowlisted).",
        fetcher.as_tool_func(),
        {"url": ArgSpec("http(s) URL", str, required=True, max_len=2048, pattern=_URL_RE),
         "refresh": ArgSpec("bypass cache", bool)},
        external=True,
    )

    def web_crawl(urls: list[str], max_workers: int = 8):
        docs = fetcher.crawl(list(urls), max_workers=max_workers)
        ok = [d for d in docs if 200 <= d.status < 300]
        return ToolResult(
            ok=bool(ok),
            data="\n\n".join(f"=== {d.url} ===\n{d.text[:2000]}" for d in ok),
            error="" if ok else "no URLs fetched successfully",
            meta={"requested": len(urls), "fetched": len(ok)},
        )

    registry.add(
        "web_crawl",
        "Fetch MANY URLs concurrently (scalable crawl; per-host rate limits preserved).",
        web_crawl,
        {"urls": ArgSpec("list of http(s) URLs", list, required=True, max_len=200),
         "max_workers": ArgSpec("parallelism (default 8)", int)},
        external=True,
    )

    def read_url(url: str, query: str = ""):
        """Fetch a long document and digest it without overflowing context."""
        from ..context import LongDocReader

        doc = fetcher.fetch(url)
        if not (200 <= doc.status < 300):
            return ToolResult(ok=False, error=f"HTTP {doc.status}")
        digest = LongDocReader(config, provider).read(doc.text, source=url)
        body = digest.synthesis
        if query:
            body += "\n\n[relevant sections]\n" + "\n---\n".join(digest.retrieve(query))
        return ToolResult(ok=True, data=body,
                          meta={"url": doc.url, "chunks": digest.n_chunks})

    registry.add(
        "read_url",
        "Read a LONG document (e.g. a full 10-K) end to end and return a bounded "
        "whole-document synthesis; with a query, also the most relevant sections.",
        read_url,
        {"url": ArgSpec("http(s) URL", str, required=True, max_len=2048, pattern=_URL_RE),
         "query": ArgSpec("optional question to retrieve specific sections", str, max_len=500)},
        external=True,
    )

    register_edgar_tools(registry, identity=config.edgar_identity)
    register_mcp_servers(registry, config.mcp_manifest)
    return registry


__all__ = [
    "Tool", "ArgSpec", "ToolRegistry", "ToolResult", "WebFetcher", "Document",
    "html_to_text", "build_toolbox", "register_edgar_tools",
    "register_mcp_servers", "load_manifest",
]
