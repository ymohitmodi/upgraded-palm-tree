"""NYX tools — the agents' hands on the outside world."""
from __future__ import annotations

from ..config import Config
from ..observability.ledger import AuditLedger
from .edgar import register_edgar_tools
from .mcp import load_manifest, register_mcp_servers
from .registry import Tool, ToolRegistry, ToolResult
from .web import Document, WebFetcher, html_to_text


def build_toolbox(config: Config, ledger: AuditLedger | None = None) -> ToolRegistry:
    """Assemble the default toolbox: web scraping + SEC EDGAR + MCP servers."""
    registry = ToolRegistry(ledger=ledger)

    fetcher = WebFetcher(
        cache_dir=config.web_cache_dir,
        user_agent=config.user_agent,
        allowed_domains=config.allowed_domains,
        rate_limit_seconds=config.web_rate_limit_seconds,
    )
    registry.add(
        "web_fetch",
        "Fetch a URL and return readable text (cached, rate-limited, allowlisted).",
        fetcher.as_tool_func(), {"url": "http(s) URL", "refresh": "bypass cache"},
    )
    register_edgar_tools(registry, identity=config.edgar_identity)
    register_mcp_servers(registry, config.mcp_manifest)
    return registry


__all__ = [
    "Tool", "ToolRegistry", "ToolResult", "WebFetcher", "Document",
    "html_to_text", "build_toolbox", "register_edgar_tools",
    "register_mcp_servers", "load_manifest",
]
