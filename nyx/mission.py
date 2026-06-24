"""Autonomous mission loop — give NYX an objective and it keeps going.

This is the connective tissue that turns the two halves of NYX into one
self-driving system:

    objective ──▶ PLAN (decompose into a backlog)
              ──▶ for each item: run the DARK FACTORY pipeline
              ──▶ every K cycles: run DARWIN evolution against productivity
              ──▶ ADOPT the improved genome back into the factory
              ──▶ repeat until the backlog is drained (or budget/cycles hit)

So: *yes* — handed an objective, NYX decomposes it, ships features through the
constitutional pipeline, periodically evolves its own agents (admitting a
variant only if it beats its ancestor), and adopts the winners so subsequent
cycles are run by better agents. It is productive and gets better as it goes,
all under the constitution and the audit ledger.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .agents.roles import build_agent
from .config import Config, load_config
from .constitution import Constitution
from .evolution.archive import Archive
from .evolution.engine import EvolutionEngine
from .memory import MemoryStore
from .observability.ledger import AuditLedger
from .observability.metrics import Metrics
from .providers import build_provider
from .providers.base import Provider
from .factory.orchestrator import Factory


@dataclass
class CycleOutcome:
    index: int
    item: str
    shipped: bool
    held: bool
    blocked_at: str | None
    gate_pass_rate: float
    calls: int


@dataclass
class MissionReport:
    objective: str
    backlog: list[str] = field(default_factory=list)
    cycles: list[CycleOutcome] = field(default_factory=list)
    evolutions: int = 0
    genome_score_before: float | None = None
    genome_score_after: float | None = None
    ledger_ok: bool = True
    budget_exhausted: bool = False
    calls: int = 0
    lessons: int = 0
    long_term_lessons: int = 0
    consolidations: int = 0

    @property
    def shipped(self) -> int:
        return sum(1 for c in self.cycles if c.shipped)

    @property
    def productivity(self) -> float:
        return round(self.shipped / len(self.cycles), 3) if self.cycles else 0.0

    @property
    def evolution_gain(self) -> float:
        if self.genome_score_before is None or self.genome_score_after is None:
            return 0.0
        return round(self.genome_score_after - self.genome_score_before, 4)

    def summary(self) -> str:
        lines = [f"Mission: {self.objective}", f"Backlog ({len(self.backlog)} items):"]
        for c in self.cycles:
            mark = "✓ shipped" if c.shipped else ("⏸ held" if c.held else f"✗ blocked@{c.blocked_at}")
            lines.append(f"  cycle {c.index}: {mark:18s} | gates {c.gate_pass_rate:.0%} | {c.item[:60]}")
        lines.append(
            f"Productivity: {self.shipped}/{len(self.cycles)} shipped ({self.productivity:.0%}) | "
            f"evolutions: {self.evolutions} | genome {self.genome_score_before}→"
            f"{self.genome_score_after} (gain {self.evolution_gain:+})"
        )
        budget = f"calls: {self.calls}" + (" (budget exhausted)" if self.budget_exhausted else "")
        lines.append(
            f"Lessons in memory: {self.lessons} ({self.long_term_lessons} long-term, "
            f"{self.consolidations} consolidations) | {budget}"
        )
        lines.append(f"Audit ledger intact: {self.ledger_ok}")
        return "\n".join(lines)


class MissionControl:
    """Drives an objective autonomously: plan → build → evolve → adopt → repeat."""

    def __init__(
        self,
        config: Config | None = None,
        provider: Provider | None = None,
        constitution: Constitution | None = None,
        ledger: AuditLedger | None = None,
        archive: Archive | None = None,
        memory: MemoryStore | None = None,
        evolve_role: str = "coder",
    ):
        self.config = config or load_config()
        self.provider = provider or build_provider(self.config)
        self.constitution = constitution or Constitution.load(
            self.config.constitution_path, mode=self.config.constitution_mode
        )
        self.ledger = ledger or AuditLedger(self.config.ledger_path)
        # Archive defines __len__, so an empty one is falsy; use `is None`.
        self.archive = archive if archive is not None else Archive(self.config.evolution_archive)
        # Semantic memory persists lessons across cycles and missions.
        self.memory = memory if memory is not None else MemoryStore(self.config.memory_path)
        self.evolve_role = evolve_role
        # One mission-level metrics object enforces a single call/spend budget
        # (Config.max_calls) across planning, every build cycle, and evolution —
        # so the autonomous loop cannot spend max_cycles * max_calls.
        self.metrics = Metrics()
        # Genomes adopted into the factory, seeded from any prior evolution.
        self.genomes: dict = {}
        self._adopt_from_archive()

    @property
    def budget_left(self) -> int:
        return max(0, self.config.max_calls - self.metrics.calls)

    def _adopt_from_archive(self) -> float | None:
        best = self.archive.best_for(self.evolve_role)
        if best:
            self.genomes[self.evolve_role] = best.to_genome()
            return best.score
        return None

    # -- planning ------------------------------------------------------------
    def plan(self, objective: str, max_items: int = 6) -> list[str]:
        planner = build_agent(
            "planner", self.config, self.provider, self.constitution,
            ledger=self.ledger, metrics=self.metrics,
        )
        # The planner's charter already says "decompose"; pass the bare objective
        # so backlog items read cleanly.
        result = planner.run(objective)
        items: list[str] = []
        for line in result.text.splitlines():
            m = re.match(r"\s*[-*]\s+(.*)", line)
            if m and m.group(1).strip():
                items.append(m.group(1).strip())
        if not items:  # robust fallback so the loop always has work
            items = [f"{objective} — milestone {i + 1}" for i in range(3)]
        self.ledger.append(
            "mission", "plan", rationale=f"{len(items)} items for: {objective[:80]}", decision="INFO"
        )
        return items[:max_items]

    # -- the loop ------------------------------------------------------------
    def run(
        self,
        objective: str,
        *,
        max_cycles: int | None = None,
        evolve_every: int = 2,
        generations: int = 4,
        keep_going: bool = False,
        autonomy: str | None = None,
        consolidate_every: int | None = None,
    ) -> MissionReport:
        if autonomy:
            self.config.autonomy = autonomy
        consolidate_every = (
            consolidate_every if consolidate_every is not None else self.config.consolidate_every
        )
        report = MissionReport(objective=objective)
        report.genome_score_before = self._adopt_from_archive()

        self.ledger.append("mission", "mission_start", rationale=objective, decision="INFO")
        backlog = self.plan(objective)
        report.backlog = list(backlog)

        idx = 0
        while backlog:
            if max_cycles is not None and idx >= max_cycles:
                break
            if self.budget_left <= 0:
                report.budget_exhausted = True
                self.ledger.append(
                    "mission", "budget_exhausted",
                    rationale=f"calls={self.metrics.calls}/{self.config.max_calls}", decision="BLOCK",
                )
                break
            item = backlog.pop(0)
            idx += 1

            # One shared metrics object => one budget across the whole mission.
            factory = Factory(
                config=self.config,
                provider=self.provider,
                constitution=self.constitution,
                ledger=self.ledger,
                metrics=self.metrics,
                genomes=self.genomes,
                memory=self.memory,
            )
            def approver(*_):
                return self.config.autonomy == "autonomous"

            # Snapshot the shared counters so we can report this cycle's deltas.
            calls0 = self.metrics.calls
            passed0, blocked0 = self.metrics.gates_passed, self.metrics.gates_blocked

            result = factory.build(item, approver=approver)

            gp = self.metrics.gates_passed - passed0
            gb = self.metrics.gates_blocked - blocked0
            report.cycles.append(
                CycleOutcome(
                    index=idx,
                    item=item,
                    shipped=result.shipped,
                    held=result.held_for_approval,
                    blocked_at=result.blocked_at,
                    gate_pass_rate=round(gp / (gp + gb), 3) if (gp + gb) else 1.0,
                    calls=self.metrics.calls - calls0,
                )
            )

            # Periodically evolve and adopt improved agents (Darwin in the loop),
            # but only while budget remains.
            if evolve_every and idx % evolve_every == 0 and self.budget_left > 0:
                self._evolve_and_adopt(generations)
                report.evolutions += 1

            # Periodically "sleep": consolidate short-term lessons into long-term
            # memory (decay, abstract recurring themes, prune the rest).
            if consolidate_every and idx % consolidate_every == 0:
                self._consolidate(report)

            # Open-ended productivity: re-plan to keep going when asked.
            if not backlog and keep_going and (max_cycles is None or idx < max_cycles):
                backlog = self.plan(f"{objective} (continue improving)")

        # A final consolidation pass at the end of the mission.
        self._consolidate(report)
        report.genome_score_after = self._adopt_from_archive() or report.genome_score_before
        report.calls = self.metrics.calls
        report.lessons = len(self.memory)
        report.long_term_lessons = self.memory.stats()["long_term"]
        report.ledger_ok = self.ledger.verify()
        self.ledger.append(
            "mission",
            "mission_end",
            rationale=f"shipped={report.shipped}/{len(report.cycles)} evolutions={report.evolutions}",
            decision="INFO",
            data={
                "productivity": report.productivity,
                "evolution_gain": report.evolution_gain,
                "calls": report.calls,
                "max_calls": self.config.max_calls,
            },
        )
        return report

    def _consolidate(self, report: MissionReport) -> None:
        stats = self.memory.consolidate()
        report.consolidations += 1
        self.ledger.append(
            "memory", "consolidate",
            rationale=(f"consolidated={stats['consolidated']} promoted={stats['promoted']} "
                       f"forgotten={stats['forgotten']} long_term={stats['long_term']}"),
            decision="INFO", data=stats,
        )

    def _evolve_and_adopt(self, generations: int) -> None:
        engine = EvolutionEngine(
            config=self.config,
            provider=self.provider,
            constitution=self.constitution,
            archive=self.archive,
            ledger=self.ledger,
            role=self.evolve_role,
            metrics=self.metrics,  # evolution shares the mission call budget
        )
        engine.evolve(generations=generations)
        best = self.archive.best_for(self.evolve_role)
        if best:
            self.genomes[self.evolve_role] = best.to_genome()
            self.ledger.append(
                "mission",
                "adopt_genome",
                rationale=f"role={self.evolve_role} score={best.score}",
                decision="PASS",
                data={"id": best.id},
            )
