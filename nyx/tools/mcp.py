"""MCP (Model Context Protocol) support — register external tool servers.

NYX can use any MCP server as a source of tools. The recommended SEC server is
`sec-edgar-mcp <https://github.com/stefanoamorelli/sec-edgar-mcp>`_ (built on
edgartools; exposes filings, XBRL-parsed financials, and Form 3/4/5 insider
trading, every response carrying the source SEC URL). Servers are declared in a
manifest (default ``.nyx/mcp.json``), in the same shape as Claude Desktop's
``mcpServers`` block, so configs are portable:

    {
      "mcpServers": {
        "sec-edgar-mcp": {
          "command": "docker",
          "args": ["run", "-i", "--rm",
                   "-e", "SEC_EDGAR_USER_AGENT=Your Name (your@email.com)",
                   "stefanoamorelli/sec-edgar-mcp:latest"]
        }
      }
    }

``MCPClient`` speaks the minimal stdio JSON-RPC needed to ``initialize``, list
tools, and call them (works with the docker/stdio server above). It's small and
best-effort: spawning a live server needs Docker + network, so the live path is
exercised in deployment, while tests cover manifest parsing only.
"""
from __future__ import annotations

import json
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

from .registry import ToolRegistry, ToolResult


@dataclass
class MCPServerSpec:
    name: str
    command: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)


def load_manifest(path: str | Path) -> list[MCPServerSpec]:
    p = Path(path)
    if not p.exists():
        return []
    data = json.loads(p.read_text(encoding="utf-8"))
    servers = data.get("mcpServers", data)  # accept either shape
    specs = []
    for name, cfg in servers.items():
        specs.append(MCPServerSpec(
            name=name, command=cfg["command"],
            args=list(cfg.get("args", [])), env=dict(cfg.get("env", {})),
        ))
    return specs


def write_sample_manifest(path: str | Path,
                          identity: str = "Your Name (your@email.com)") -> Path:
    """Write a ready-to-edit manifest registering the sec-edgar-mcp server.

    Uses the project's recommended Docker/stdio invocation
    (https://github.com/stefanoamorelli/sec-edgar-mcp). SEC requires a real
    contact in ``SEC_EDGAR_USER_AGENT`` (format: ``Name (email)``)."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({
        "mcpServers": {
            "sec-edgar-mcp": {
                "command": "docker",
                "args": [
                    "run", "-i", "--rm",
                    "-e", f"SEC_EDGAR_USER_AGENT={identity}",
                    "stefanoamorelli/sec-edgar-mcp:latest",
                ],
            }
        }
    }, indent=2), encoding="utf-8")
    return p


class MCPClient:
    """Minimal stdio JSON-RPC client for a single MCP server."""

    def __init__(self, spec: MCPServerSpec, timeout: float = 30.0):
        self.spec = spec
        self.timeout = timeout
        self._proc: subprocess.Popen | None = None
        self._id = 0

    def __enter__(self):  # pragma: no cover - requires a live server
        import os

        env = {**os.environ, **self.spec.env}
        self._proc = subprocess.Popen(
            [self.spec.command, *self.spec.args],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, env=env, bufsize=1,
        )
        self._rpc("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {}, "clientInfo": {"name": "nyx", "version": "0.1"},
        })
        self._notify("notifications/initialized", {})
        return self

    def __exit__(self, *exc):  # pragma: no cover
        if self._proc:
            self._proc.terminate()

    def _readline(self, deadline: float) -> str:  # pragma: no cover - live only
        """Read one stdout line, enforcing the client timeout (POSIX select)."""
        import select

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError(f"MCP server '{self.spec.name}' timed out")
        ready, _, _ = select.select([self._proc.stdout], [], [], remaining)
        if not ready:
            self._proc.terminate()
            raise TimeoutError(f"MCP server '{self.spec.name}' timed out after {self.timeout}s")
        return self._proc.stdout.readline()

    def _rpc(self, method: str, params: dict) -> dict:  # pragma: no cover - live only
        self._id += 1
        msg = {"jsonrpc": "2.0", "id": self._id, "method": method, "params": params}
        self._proc.stdin.write(json.dumps(msg) + "\n")
        self._proc.stdin.flush()
        deadline = time.monotonic() + self.timeout
        while True:
            line = self._readline(deadline)
            if not line:
                raise RuntimeError("MCP server closed without responding")
            resp = json.loads(line)
            if resp.get("id") == self._id:
                if "error" in resp:
                    raise RuntimeError(resp["error"])
                return resp.get("result", {})

    def _notify(self, method: str, params: dict) -> None:  # pragma: no cover - live only
        self._proc.stdin.write(json.dumps(
            {"jsonrpc": "2.0", "method": method, "params": params}) + "\n")
        self._proc.stdin.flush()

    def list_tools(self) -> list[dict]:  # pragma: no cover - live only
        return self._rpc("tools/list", {}).get("tools", [])

    def call_tool(self, name: str, arguments: dict) -> ToolResult:  # pragma: no cover - live only
        result = self._rpc("tools/call", {"name": name, "arguments": arguments})
        parts = [c.get("text", "") for c in result.get("content", []) if c.get("type") == "text"]
        return ToolResult(ok=not result.get("isError"), data="\n".join(parts))


def register_mcp_servers(registry: ToolRegistry, manifest_path: str | Path) -> list[str]:
    """Register a thin proxy tool per configured MCP server (lazy connect)."""
    registered = []
    for spec in load_manifest(manifest_path):
        def _make(spec: MCPServerSpec):
            def mcp_call(tool: str, arguments: dict | None = None) -> ToolResult:  # pragma: no cover
                with MCPClient(spec) as client:
                    return client.call_tool(tool, arguments or {})
            return mcp_call

        from .registry import ArgSpec

        registry.add(
            f"mcp.{spec.name}",
            f"Call a tool on the '{spec.name}' MCP server (e.g. sec-edgar-mcp: "
            "filings, XBRL financials, Form 3/4/5 insider trading).",
            _make(spec),
            {"tool": ArgSpec("tool name on the server", str, required=True, max_len=128),
             "arguments": ArgSpec("dict of args for that tool", dict)},
            external=True,   # MCP output is untrusted → injection-classified
        )
        registered.append(spec.name)
    return registered
