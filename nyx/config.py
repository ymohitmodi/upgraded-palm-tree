"""Factory configuration.

Loads from environment variables (and an optional ``.env`` file) with safe
defaults. With no ``OLLAMA_API_KEY`` set, the factory runs in deterministic
MOCK mode so the whole architecture works offline.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _load_dotenv(path: str = ".env") -> None:
    """Minimal .env loader (no external dependency). Does not override real env."""
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


@dataclass
class Config:
    """Resolved factory configuration."""

    # Brain / provider
    ollama_api_key: str = ""
    ollama_host: str = "https://ollama.com"
    model_architect: str = "qwen3.5-coder:480b-cloud"
    model_coder: str = "qwen3.5-coder:480b-cloud"
    model_reviewer: str = "glm-5.1:cloud"
    model_fast: str = "gemma4:cloud"

    # Factory behavior
    fanout: int = 3
    autonomy: str = "supervised"  # assisted | supervised | autonomous
    max_calls: int = 200

    # Constitution
    constitution_path: str = "constitution/constitution.yaml"
    constitution_mode: str = "block"  # block | warn

    # Evolution
    evolution_archive: str = ".nyx/evolution_archive"
    evolution_threshold: float = 0.02

    # Observability
    ledger_path: str = ".nyx/audit.ledger.jsonl"
    log_level: str = "INFO"

    # Memory (semantic lessons)
    memory_path: str = ".nyx/memory.jsonl"
    # Working-memory compaction: max chars of context carried between stages.
    context_char_budget: int = 4000
    # Consolidation ("sleep"): run a consolidation pass every N build cycles.
    consolidate_every: int = 5

    # Tools / connectivity (live data; see docs/TOOLS.md)
    user_agent: str = "nyx-dark-factory/0.1 (+research; contact@example.com)"
    edgar_identity: str = ""               # "Your Name your.email@example.com" for SEC
    web_cache_dir: str = ".nyx/webcache"
    web_rate_limit_seconds: float = 1.0    # min delay between hits to the same host
    # Allowlist of domains the scraper may fetch (empty = allow all, use with care).
    allowed_domains: tuple[str, ...] = ()
    mcp_manifest: str = ".nyx/mcp.json"    # registered MCP servers

    model_for_role: dict[str, str] = field(default_factory=dict)

    @property
    def mock_mode(self) -> bool:
        """True when there is no key, so cognition is served by the MockProvider."""
        return not self.ollama_api_key

    def model(self, role: str) -> str:
        """Resolve a model name for a logical role (architect/coder/reviewer/fast)."""
        return self.model_for_role.get(role, self.model_fast)


def load_config(dotenv: bool = True) -> Config:
    """Build a :class:`Config` from environment (and optional ``.env``)."""
    if dotenv:
        _load_dotenv(os.environ.get("NYX_DOTENV", ".env"))

    def _int(name: str, default: int) -> int:
        try:
            return int(os.environ.get(name, default))
        except (TypeError, ValueError):
            return default

    def _float(name: str, default: float) -> float:
        try:
            return float(os.environ.get(name, default))
        except (TypeError, ValueError):
            return default

    cfg = Config(
        ollama_api_key=os.environ.get("OLLAMA_API_KEY", "").strip(),
        ollama_host=os.environ.get("OLLAMA_HOST", "https://ollama.com").rstrip("/"),
        model_architect=os.environ.get("NYX_MODEL_ARCHITECT", "qwen3.5-coder:480b-cloud"),
        model_coder=os.environ.get("NYX_MODEL_CODER", "qwen3.5-coder:480b-cloud"),
        model_reviewer=os.environ.get("NYX_MODEL_REVIEWER", "glm-5.1:cloud"),
        model_fast=os.environ.get("NYX_MODEL_FAST", "gemma4:cloud"),
        fanout=_int("NYX_FANOUT", 3),
        autonomy=os.environ.get("NYX_AUTONOMY", "supervised").lower(),
        max_calls=_int("NYX_MAX_CALLS", 200),
        constitution_path=os.environ.get("NYX_CONSTITUTION", "constitution/constitution.yaml"),
        constitution_mode=os.environ.get("NYX_CONSTITUTION_MODE", "block").lower(),
        evolution_archive=os.environ.get("NYX_EVOLUTION_ARCHIVE", ".nyx/evolution_archive"),
        evolution_threshold=_float("NYX_EVOLUTION_THRESHOLD", 0.02),
        ledger_path=os.environ.get("NYX_LEDGER", ".nyx/audit.ledger.jsonl"),
        log_level=os.environ.get("NYX_LOG_LEVEL", "INFO").upper(),
        memory_path=os.environ.get("NYX_MEMORY", ".nyx/memory.jsonl"),
        context_char_budget=int(os.environ.get("NYX_CONTEXT_BUDGET", "4000")),
        consolidate_every=int(os.environ.get("NYX_CONSOLIDATE_EVERY", "5")),
        user_agent=os.environ.get(
            "NYX_USER_AGENT", "nyx-dark-factory/0.1 (+research; contact@example.com)"
        ),
        edgar_identity=os.environ.get("EDGAR_IDENTITY", ""),
        web_cache_dir=os.environ.get("NYX_WEB_CACHE", ".nyx/webcache"),
        web_rate_limit_seconds=float(os.environ.get("NYX_WEB_RATE_LIMIT", "1.0")),
        allowed_domains=tuple(
            d.strip() for d in os.environ.get("NYX_ALLOWED_DOMAINS", "").split(",") if d.strip()
        ),
        mcp_manifest=os.environ.get("NYX_MCP_MANIFEST", ".nyx/mcp.json"),
    )
    cfg.model_for_role = {
        "architect": cfg.model_architect,
        "coder": cfg.model_coder,
        "reviewer": cfg.model_reviewer,
        "fast": cfg.model_fast,
    }
    return cfg
