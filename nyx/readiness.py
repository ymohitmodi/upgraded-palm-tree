"""Go-live readiness — a preflight check before running a capability for real.

`nyx doctor` verifies the framework loads; this verifies the *live* dependencies
(brain key, EDGAR identity, data reachability, Docker, fail-closed governance)
are actually in place, with a concrete fix for each gap. Config/env/import checks
run offline; network reachability and a tiny live model probe run only with
``probe=True`` so the default check is fast and deterministic.
"""
from __future__ import annotations

import shutil
import socket
from dataclasses import dataclass

PASS, WARN, FAIL = "PASS", "WARN", "FAIL"


@dataclass
class Check:
    name: str
    status: str
    detail: str = ""
    fix: str = ""


def _reachable(host: str, port: int = 443, timeout: float = 3.0) -> bool:  # pragma: no cover - network
    try:
        socket.create_connection((host, port), timeout=timeout).close()
        return True
    except OSError:
        return False


def _module_available(name: str) -> bool:
    import importlib.util

    return importlib.util.find_spec(name) is not None


def preflight(config, capability: str | None = None, *, probe: bool = False) -> list[Check]:
    """Return readiness checks for running `capability` (or general) live."""
    checks: list[Check] = []

    # -- brain ---------------------------------------------------------------
    if config.mock_mode:
        checks.append(Check("brain", WARN, "MOCK mode (no OLLAMA_API_KEY) — stub outputs",
                            "export OLLAMA_API_KEY=... to use the real model"))
    else:
        checks.append(Check("brain", PASS, f"Ollama Cloud @ {config.ollama_host}"))
        if probe:  # pragma: no cover - network
            checks.append(_probe_brain(config))

    # -- governance ----------------------------------------------------------
    checks.append(Check("governance", PASS if config.constitution_mode == "block" else WARN,
                        f"constitution_mode={config.constitution_mode}",
                        "" if config.constitution_mode == "block"
                        else "set NYX_CONSTITUTION_MODE=block for fail-closed gates"))
    checks.append(Check("budget", PASS if config.max_calls > 0 else WARN,
                        f"max_calls={config.max_calls}",
                        "" if config.max_calls > 0 else "set NYX_MAX_CALLS to bound spend"))

    # -- memory embeddings ---------------------------------------------------
    checks.append(Check("embeddings",
                        PASS if not config.mock_mode else WARN,
                        f"model={config.model_embed}" + ("" if not config.mock_mode
                                                         else " (hashing fallback in mock)"),
                        "" if not config.mock_mode else "a live key enables semantic embeddings"))

    # -- capability-specific -------------------------------------------------
    if capability == "value-investing":
        checks.extend(_investing_checks(config, probe))

    # -- scratch dir ---------------------------------------------------------
    from pathlib import Path

    try:
        Path(config.ledger_path).parent.mkdir(parents=True, exist_ok=True)
        checks.append(Check("state-dir", PASS, str(Path(config.ledger_path).parent)))
    except OSError as exc:
        checks.append(Check("state-dir", FAIL, str(exc), "ensure the .nyx directory is writable"))

    return checks


def _investing_checks(config, probe: bool) -> list[Check]:
    out = [
        Check("edgar-identity", PASS if config.edgar_identity else FAIL,
              config.edgar_identity or "not set",
              "" if config.edgar_identity else "export EDGAR_IDENTITY='Name email' (SEC requires it)"),
        Check("edgartools", PASS if _module_available("edgar") else FAIL,
              "installed" if _module_available("edgar") else "missing",
              "" if _module_available("edgar") else "pip install -e '.[investing]'"),
        Check("docker (MCP)", PASS if shutil.which("docker") else WARN,
              "found" if shutil.which("docker") else "not found",
              "" if shutil.which("docker") else "install Docker to run sec-edgar-mcp (optional)"),
    ]
    allow = config.allowed_domains
    needed = ("sec.gov", "stooq.com")
    if allow and not all(any(d == n or d.endswith(n) for d in allow) for n in needed):
        out.append(Check("egress-allowlist", WARN, f"allowed_domains={list(allow)}",
                         "add sec.gov and stooq.com to NYX_ALLOWED_DOMAINS for live data"))
    else:
        out.append(Check("egress-allowlist", PASS,
                         "sec.gov + stooq.com permitted" if allow else "open (no allowlist)"))
    if probe:  # pragma: no cover - network
        for host in ("www.sec.gov", "stooq.com"):
            ok = _reachable(host)
            out.append(Check(f"reach:{host}", PASS if ok else FAIL,
                             "reachable" if ok else "unreachable",
                             "" if ok else f"allow {host} in your network policy or run on open internet"))
    return out


def _probe_brain(config) -> Check:  # pragma: no cover - network
    try:
        from .providers import build_provider
        from .providers.base import ChatMessage

        r = build_provider(config).chat(config.model("fast"),
                                        [ChatMessage(role="user", content="ping")], max_tokens=1)
        return Check("brain-probe", PASS, f"responded ({r.model})")
    except Exception as exc:  # noqa: BLE001
        return Check("brain-probe", FAIL, str(exc)[:80], "check OLLAMA_API_KEY / host / network")


def verdict(checks: list[Check]) -> str:
    if any(c.status == FAIL for c in checks):
        return FAIL
    if any(c.status == WARN for c in checks):
        return WARN
    return PASS
