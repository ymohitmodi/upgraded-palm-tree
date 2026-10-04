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
class ArgSpec:
    """Typed validation for a tool argument (OWASP LLM07: validate tool inputs)."""
    description: str = ""
    type: type = str
    required: bool = False
    max_len: int | None = None
    pattern: str | None = None          # regex the (stringified) value must match

    def validate(self, name: str, value) -> str | None:
        """Return an error string if invalid, else None."""
        if not isinstance(value, self.type) and not (
            self.type is float and isinstance(value, int)):
            return f"{name}: expected {self.type.__name__}, got {type(value).__name__}"
        if self.max_len is not None and hasattr(value, "__len__") and len(value) > self.max_len:
            return f"{name}: exceeds max length {self.max_len}"
        if self.pattern is not None:
            import re
            if not re.fullmatch(self.pattern, str(value)):
                return f"{name}: does not match required format"
        return None


@dataclass
class Tool:
    name: str
    description: str
    func: Callable[..., ToolResult]
    schema: dict = field(default_factory=dict)   # arg name -> description | ArgSpec
    external: bool = False                        # output is untrusted (web/filings)

    def validate_args(self, kwargs: dict) -> str | None:
        specs = {k: v for k, v in self.schema.items() if isinstance(v, ArgSpec)}
        for name, spec in specs.items():
            if name not in kwargs:
                if spec.required:
                    return f"{name}: required argument missing"
                continue
            err = spec.validate(name, kwargs[name])
            if err:
                return err
        return None


class ToolRegistry:
    def __init__(self, ledger: AuditLedger | None = None, config=None, provider=None):
        self._tools: dict[str, Tool] = {}
        self.ledger = ledger
        self.config = config          # enables the LLM injection classifier on
        self.provider = provider      # external tool outputs when a brain is live
        self._allowed: set[str] | None = None   # None = all tools permitted

    def set_allowed(self, names) -> None:
        """Restrict callable tools to ``names`` (least privilege). None = all.

        An entry ending in ``*`` is a prefix wildcard, so a capability can grant
        every dynamically-registered MCP tool with ``"mcp.*"`` without naming
        each server."""
        self._allowed = set(names) if names is not None else None

    def _permitted(self, name: str) -> bool:
        if self._allowed is None:
            return True
        if name in self._allowed:
            return True
        return any(a.endswith("*") and name.startswith(a[:-1]) for a in self._allowed)

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def add(self, name: str, description: str, func, schema: dict | None = None,
            external: bool = False) -> None:
        self.register(Tool(name=name, description=description, func=func,
                           schema=schema or {}, external=external))

    def names(self) -> list[str]:
        return sorted(self._tools)

    def list(self) -> list[Tool]:
        return [self._tools[n] for n in self.names()]

    def describe(self) -> str:
        """A compact catalog for injecting into an agent's prompt."""
        lines = []
        for t in self.list():
            parts = []
            for k, v in t.schema.items():
                desc = v.description if isinstance(v, ArgSpec) else v
                req = "*" if isinstance(v, ArgSpec) and v.required else ""
                parts.append(f"{k}{req}: {desc}")
            lines.append(f"- {t.name}({', '.join(parts)}) — {t.description}")
        return "\n".join(lines) if lines else "(no tools available)"

    def call(self, name: str, **kwargs) -> ToolResult:
        tool = self._tools.get(name)
        if tool is None:
            return ToolResult(ok=False, error=f"unknown tool: {name}")
        if not self._permitted(name):
            if self.ledger is not None:
                self.ledger.append("tools", f"deny:{name}",
                                   rationale="tool not permitted for this capability",
                                   decision="BLOCK")
            return ToolResult(ok=False, error=f"tool '{name}' not permitted (least privilege)")
        # Validate arguments against the typed schema before executing.
        arg_error = tool.validate_args(kwargs)
        if arg_error is not None:
            return ToolResult(ok=False, error=f"invalid arguments: {arg_error}")
        t0 = time.time()
        try:
            result = tool.func(**kwargs)
        except Exception as exc:  # noqa: BLE001 — tools must never crash the factory
            result = ToolResult(ok=False, error=f"{type(exc).__name__}: {exc}")
        # Guardrail: never let a tool surface secrets into the agent context.
        if result.ok and isinstance(result.data, str) and scan_secrets(result.data):
            result = ToolResult(ok=False, error="tool output blocked: contains secret-like content")
        # External tool output is untrusted: classify for prompt injection and,
        # if flagged, neutralize (wrap as inert data) rather than pass it through.
        injection_flag = False
        if result.ok and tool.external and isinstance(result.data, str) and result.data:
            from ..security.injection_classifier import classify_injection, neutralize

            verdict = classify_injection(result.data, self.config, self.provider)
            if verdict.is_injection:
                injection_flag = True
                result.data = neutralize(result.data, verdict)
                result.meta = {**result.meta, "injection": verdict.reason}
        if self.ledger is not None:
            self.ledger.append(
                actor="tools",
                action=f"call:{name}",
                rationale=("injection-neutralized " if injection_flag else "")
                + (result.error or "ok")[:120],
                decision="PASS" if result.ok else "BLOCK",
                data={"args": list(kwargs), "ms": round((time.time() - t0) * 1000),
                      "injection": injection_flag},
            )
        return result
