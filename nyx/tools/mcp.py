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
import queue
import subprocess
import threading
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


def write_edgartools_manifest(path: str | Path, identity: str = "Your Name your@email.com",
                              python_exe: str | None = None) -> Path:
    """Write a manifest registering the pip-installed ``edgartools`` MCP server
    (https://github.com/sareegpt/edgartools-mcp), launched via ``python -m edgar.ai``.

    Preferred over the Docker server on a mini-PC: no Docker, and it reuses the
    same ``edgartools[ai]`` already installed for the investing capability. It
    exposes the full SEC surface — XBRL financials, 13F holdings, Form 4 insider
    trades, 8-K events, and standardized facts. ``python_exe`` defaults to the
    current interpreter so it keeps working when NYX runs detached (as a service),
    where ``python`` on PATH may differ."""
    import sys

    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({
        "mcpServers": {
            "edgartools": {
                "command": python_exe or sys.executable,
                "args": ["-m", "edgar.ai"],
                "env": {"EDGAR_IDENTITY": identity},
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
        self._queue: "queue.Queue[str]" = queue.Queue()
        self._reader: threading.Thread | None = None

    def start(self):  # pragma: no cover - requires a live server
        """Spawn the server, handshake, and become ready to call tools."""
        import os

        env = {**os.environ, **self.spec.env}
        self._proc = subprocess.Popen(
            [self.spec.command, *self.spec.args],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, env=env, bufsize=1,
        )
        # A background reader drains stdout into a queue. This is cross-platform
        # (Windows has no select() on pipes) and lets _rpc enforce a timeout via
        # queue.get(timeout=…) without blocking forever on a silent server.
        self._reader = threading.Thread(target=self._drain, daemon=True)
        self._reader.start()
        self._rpc("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {}, "clientInfo": {"name": "nyx", "version": "0.1"},
        })
        self._notify("notifications/initialized", {})
        return self

    def close(self):  # pragma: no cover
        if self._proc:
            self._proc.terminate()
            self._proc = None

    @property
    def alive(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def __enter__(self):  # pragma: no cover - requires a live server
        return self.start()

    def __exit__(self, *exc):  # pragma: no cover
        self.close()

    def _drain(self) -> None:  # pragma: no cover - live only
        """Read the server's stdout line-by-line into the queue until it closes."""
        try:
            for line in self._proc.stdout:
                self._queue.put(line)
        except (ValueError, OSError):
            pass  # stdout closed on terminate — nothing more to read

    def _readline(self, deadline: float) -> str:  # pragma: no cover - live only
        """Return the next stdout line, enforcing the client timeout (any OS)."""
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            self._proc.terminate()
            raise TimeoutError(f"MCP server '{self.spec.name}' timed out after {self.timeout}s")
        try:
            return self._queue.get(timeout=remaining)
        except queue.Empty:
            self._proc.terminate()
            raise TimeoutError(
                f"MCP server '{self.spec.name}' timed out after {self.timeout}s") from None

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
    """Register a thin proxy tool per configured MCP server.

    The connection is **persistent**: the server is spawned once on first use and
    reused for every subsequent call (a fresh spawn costs seconds — far too slow
    for an autonomous loop that reads many filings). A dead process is transparently
    respawned, and all clients are terminated at interpreter exit."""
    import atexit

    registered = []
    for spec in load_manifest(manifest_path):
        def _make(spec: MCPServerSpec):
            state: dict = {"client": None}

            def _client() -> MCPClient:  # pragma: no cover - live only
                client = state["client"]
                if client is None or not client.alive:
                    client = MCPClient(spec).start()
                    state["client"] = client
                    atexit.register(client.close)
                return client

            def mcp_call(tool: str, arguments: dict | None = None) -> ToolResult:  # pragma: no cover
                try:
                    return _client().call_tool(tool, arguments or {})
                except (BrokenPipeError, RuntimeError, TimeoutError):
                    # Server died mid-call — drop it and retry once on a fresh spawn.
                    if state["client"]:
                        state["client"].close()
                    state["client"] = None
                    return _client().call_tool(tool, arguments or {})
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
