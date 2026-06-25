"""Pluggable, goal-specific capabilities.

A **Capability** packages everything NYX needs to pursue one kind of goal:
which objectives it handles, the agent role + doctrine to evolve, the fitness
benchmark, the constitution gates, the knowledge to seed/refresh, and what one
"cycle" actually *does* (e.g. read filings → decide a shortlist).

The generic :class:`CapabilityRunner` drives any capability autonomously —
plan → refresh knowledge → execute → reflect → recall → evolve → consolidate →
repeat — reusing NYX's memory, evolution, budget, and audit machinery. To add a
new goal (legal research, biotech screening, …) implement ``Capability`` and
register it; nothing else changes.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # avoid import cycles at runtime
    from ..config import Config
    from ..constitution import Constitution
    from ..memory import MemoryStore
    from ..observability.ledger import AuditLedger
    from ..observability.metrics import Metrics
    from ..providers.base import Provider
    from ..tools.registry import ToolRegistry


@dataclass
class CycleContext:
    """Everything a capability needs to act during one cycle."""
    config: "Config"
    memory: "MemoryStore"
    ledger: "AuditLedger"
    metrics: "Metrics"
    toolbox: "ToolRegistry"
    constitution: "Constitution"
    provider: "Provider | None" = None
    genomes: dict = field(default_factory=dict)   # role -> adopted Genome
    lessons: list[str] = field(default_factory=list)  # recalled this cycle
    cycle_index: int = 0


@dataclass
class CycleResult:
    item: str
    ok: bool = True
    summary: str = ""
    score: float | None = None
    findings: list[str] = field(default_factory=list)
    blocked_at: str | None = None
    # Lessons the capability wants written to memory (text, kind, tags).
    lessons: list[tuple[str, str, list[str]]] = field(default_factory=list)


class Capability(ABC):
    """Base class for a goal-specific capability."""

    name: str = "capability"
    description: str = ""

    # --- routing ---
    @abstractmethod
    def matches(self, objective: str) -> bool:
        """True if this capability should handle the given objective."""

    # --- evolution wiring ---
    def evolve_role(self) -> str:
        return "coder"

    def directives(self) -> list[str] | None:
        """Domain directive pool for mutation (None = software default)."""
        return None

    def benchmark(self, ctx: CycleContext):
        """A fitness benchmark for the EvolutionEngine, or None for the default."""
        return None

    # --- governance & knowledge ---
    def constitution(self, base: "Constitution") -> "Constitution":
        """Return the constitution to enforce (may add domain gates)."""
        return base

    def seed_memory(self, memory: "MemoryStore") -> int:
        """Seed durable doctrine into long-term memory once. Returns count."""
        return 0

    def refresh_knowledge(self, ctx: CycleContext) -> dict:
        """Keep reading the world (e.g. SEC filings, annual reports). Best-effort."""
        return {}

    # --- planning & acting ---
    def plan(self, objective: str, ctx: CycleContext) -> list[str]:
        """Decompose the objective into a backlog of cycle tasks."""
        return [f"{objective} — cycle {i + 1}" for i in range(3)]

    @abstractmethod
    def execute(self, task: str, ctx: CycleContext) -> CycleResult:
        """Do the work for one backlog item and (for investing) make a decision."""
