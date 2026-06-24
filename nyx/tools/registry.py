"""Tool registry — how NYX agents reach the outside world.

A `Tool` is a named, described capability (fetch a web page, pull SEC
financials, call an MCP server). The `ToolRegistry` is the agent's "hands": it
lists available tools for prompting, and every call is **guardrailed** (output
scanned for secrets/injection) and **audited** to the ledger — tool use is a
consequential action, so it is governed exactly like everything else in NYX.

Tools are dependency-light and degrade gracefully: if an optional backend
(``requests``, ``edgartools``, a running MCP server) is absent, the tool returns
a clear, structured error instead of crashing the factory.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable

from ..observability.ledger import AuditLedger
from ..security.guardrails import scan_secrets


@dataclass
class ToolResult:
    ok: bool
    data: Any = None
    error: str = ""
    meta: dict = field(default_factory=dict)

    def text(self, limit: int = 4000) -> str:
        if not self.ok:
            return f"[tool error] {self.error}"
        s = self.data if isinstance(self.data, str) else repr(self.data)
        return s[:limit]


@dataclass
class Tool:
    name: str
    description: str
    func: Callable[..., ToolResult]
    schema: dict = field(default_factory=dict)   # arg name -> description


class ToolRegistry:
    def __init__(self, ledger: AuditLedger | None = None):
        self._tools: dict[str, Tool] = {}
        self.ledger = ledger

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def add(self, name: str, description: str, func, schema: dict | None = None) -> None:
        self.register(Tool(name=name, description=description, func=func, schema=schema or {}))

    def names(self) -> list[str]:
        return sorted(self._tools)

    def list(self) -> list[Tool]:
        return [self._tools[n] for n in self.names()]

    def describe(self) -> str:
        """A compact catalog for injecting into an agent's prompt."""
        lines = []
        for t in self.list():
            args = ", ".join(f"{k}: {v}" for k, v in t.schema.items())
            lines.append(f"- {t.name}({args}) — {t.description}")
        return "\n".join(lines) if lines else "(no tools available)"

    def call(self, name: str, **kwargs) -> ToolResult:
        tool = self._tools.get(name)
        if tool is None:
            return ToolResult(ok=False, error=f"unknown tool: {name}")
        t0 = time.time()
        try:
            result = tool.func(**kwargs)
        except Exception as exc:  # noqa: BLE001 — tools must never crash the factory
            result = ToolResult(ok=False, error=f"{type(exc).__name__}: {exc}")
        # Guardrail: never let a tool surface secrets into the agent context.
        if result.ok and isinstance(result.data, str) and scan_secrets(result.data):
            result = ToolResult(ok=False, error="tool output blocked: contains secret-like content")
        if self.ledger is not None:
            self.ledger.append(
                actor="tools",
                action=f"call:{name}",
                rationale=(result.error or "ok")[:120],
                decision="PASS" if result.ok else "BLOCK",
                data={"args": list(kwargs), "ms": round((time.time() - t0) * 1000)},
            )
        return result
