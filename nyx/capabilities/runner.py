"""CapabilityRunner — the goal-agnostic autonomous loop.

plan → (refresh knowledge) → execute → reflect → recall → (evolve) →
(consolidate) → repeat, until the backlog empties or the call/spend budget runs
out. Reuses NYX's memory, evolution archive, audit ledger, and budget so every
capability gets continual learning + governance for free.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..config import Config, load_config
from ..constitution import Constitution
from ..evolution.archive import Archive
from ..evolution.engine import EvolutionEngine
from ..memory import MemoryStore
from ..observability.ledger import AuditLedger
from ..observability.metrics import Metrics
from ..providers import build_provider
from ..tools import build_toolbox
from .base import Capability, CycleContext, CycleResult


@dataclass
class RunReport:
    objective: str
    capability: str
    cycles: list[CycleResult] = field(default_factory=list)
    evolutions: int = 0
    consolidations: int = 0
    knowledge_refreshes: int = 0
    genome_score_before: float | None = None
    genome_score_after: float | None = None
    lessons: int = 0
    long_term_lessons: int = 0
    calls: int = 0
    budget_exhausted: bool = False
    ledger_ok: bool = True

    def summary(self) -> str:
        lines = [f"Objective: {self.objective}", f"Capability: {self.capability}"]
        for c in self.cycles:
            mark = "✓" if c.ok else f"✗@{c.blocked_at}"
            extra = f" | score {c.score}" if c.score is not None else ""
            lines.append(f"  cycle {c.item[:54]:54s} {mark}{extra}")
        lines.append(
            f"Decisions: {len(self.cycles)} | evolutions: {self.evolutions} "
            f"(genome {self.genome_score_before}→{self.genome_score_after}) | "
            f"knowledge refreshes: {self.knowledge_refreshes}"
        )
        budget = f"calls: {self.calls}" + (" (budget exhausted)" if self.budget_exhausted else "")
        lines.append(f"Memory: {self.lessons} lessons ({self.long_term_lessons} long-term, "
                     f"{self.consolidations} consolidations) | {budget}")
        lines.append(f"Audit ledger intact: {self.ledger_ok}")
        return "\n".join(lines)


class CapabilityRunner:
    def __init__(
        self,
        capability: Capability,
        config: Config | None = None,
        provider=None,
        ledger: AuditLedger | None = None,
        memory: MemoryStore | None = None,
        archive: Archive | None = None,
    ):
        self.cap = capability
        self.config = config or load_config()
        self.provider = provider or build_provider(self.config)
        self.ledger = ledger or AuditLedger(self.config.ledger_path)
        if memory is not None:
            self.memory = memory
        else:
            from pathlib import Path

            from ..embeddings import embedder_for
            memory_path = self.config.memory_path
            if self.config.memory_per_capability:
                # Compartment per capability: the investor's filings research and
                # the advisor's dossier lessons live in separate stores, so recall
                # never surfaces another domain's noise and each file stays small.
                p = Path(memory_path)
                memory_path = str(p.with_name(f"{p.stem}-{self.cap.name}{p.suffix}"))
            self.memory = MemoryStore(memory_path,
                                      embedder=embedder_for(self.config, self.provider))
            # Federate sibling capability stores for cross-domain DOCTRINE recall
            # (trusted long-term principles only): Buffett's lens can sharpen an
            # EB-1A agenda; research rigor can sharpen a stock memo.
            if self.config.memory_per_capability:
                self._attach_sibling_doctrine(Path(self.config.memory_path))
        self.archive = archive if archive is not None else Archive(self.config.evolution_archive)
        self.metrics = Metrics()
        base = Constitution.load(self.config.constitution_path, mode=self.config.constitution_mode)
        self.constitution = self.cap.constitution(base)
        self.toolbox = build_toolbox(self.config, ledger=self.ledger, provider=self.provider)
        self.toolbox.set_allowed(self.cap.allowed_tools())  # least privilege per capability
        from ..context_broker import ContextBroker
        self._broker = ContextBroker(budget_chars=max(800, self.config.context_char_budget // 2))
        self.genomes: dict = {}

    def _attach_sibling_doctrine(self, base) -> None:
        from ..embeddings import embedder_for
        own = str(self.memory.path)
        embedder = embedder_for(self.config, self.provider)
        siblings = [MemoryStore(p, embedder=embedder)
                    for p in sorted(base.parent.glob(f"{base.stem}-*{base.suffix}"))
                    if str(p) != own]
        if siblings:
            self.memory.attach_doctrine(*siblings)

    @property
    def budget_left(self) -> int:
        return max(0, self.config.max_calls - self.metrics.calls)

    def _ctx(self, cycle_index: int = 0) -> CycleContext:
        return CycleContext(
            config=self.config, memory=self.memory, ledger=self.ledger, metrics=self.metrics,
            toolbox=self.toolbox, constitution=self.constitution, provider=self.provider,
            genomes=self.genomes, cycle_index=cycle_index,
        )

    def _adopt(self) -> float | None:
        best = self.archive.best_for(self.cap.evolve_role())
        if best:
            self.genomes[self.cap.evolve_role()] = best.to_genome()
            return best.score
        return None

    # -- public surface for one-shot commands (e.g. `nyx screen`) -------------
    def adopt_best(self) -> float | None:
        """Load the best evolved genome from the archive; returns its score (or None)."""
        return self._adopt()

    def context(self, cycle_index: int = 0) -> CycleContext:
        """A ready cycle context (memory, ledger, toolbox, constitution, provider)."""
        return self._ctx(cycle_index)

    def run(
        self,
        objective: str,
        *,
        max_cycles: int | None = 6,
        evolve_every: int = 2,
        generations: int = 6,
        refresh_every: int = 1,
        consolidate_every: int | None = None,
        keep_going: bool = False,
        hours: float | None = None,
    ) -> RunReport:
        """Drive the capability. ``hours`` adds a wall-clock budget for lights-out
        missions (with ``keep_going`` + unlimited cycles it runs for days,
        compounding memory and evolution until time or the call budget ends)."""
        import time as _time

        deadline = (_time.monotonic() + hours * 3600) if hours else None
        consolidate_every = (consolidate_every if consolidate_every is not None
                             else self.config.consolidate_every)
        report = RunReport(objective=objective, capability=self.cap.name)
        self.ledger.append("capability", "run_start",
                           rationale=f"{self.cap.name}: {objective}", decision="INFO")

        # One-time doctrine seed + baseline genome.
        seeded = self.cap.seed_memory(self.memory)
        if seeded:
            self.ledger.append("capability", "seed_memory",
                               rationale=f"{seeded} principles", decision="INFO")
        report.genome_score_before = self._adopt()

        backlog = self.cap.plan(objective, self._ctx())
        idx = 0
        while backlog:
            if max_cycles is not None and idx >= max_cycles:
                break
            if deadline is not None and _time.monotonic() >= deadline:
                self.ledger.append("capability", "time_budget_reached",
                                   rationale=f"{hours}h wall clock", decision="INFO")
                break
            if self.budget_left <= 0:
                report.budget_exhausted = True
                self.ledger.append("capability", "budget_exhausted", decision="BLOCK")
                break
            item = backlog.pop(0)
            idx += 1
            ctx = self._ctx(idx)

            # Keep reading the world (SEC filings, annual reports, …).
            if refresh_every and idx % refresh_every == 0:
                stats = self.cap.refresh_knowledge(ctx)
                if stats:
                    report.knowledge_refreshes += 1
                    self.ledger.append("capability", "refresh_knowledge",
                                       rationale=str(stats)[:120], decision="INFO")

            # Discover the internal context this goal needs (multi-probe), kept
            # lean by the broker (relevance floor + dedup + budget) so the agent
            # isn't polluted with low-signal snippets.
            bundle = self._broker.assemble(item, self.memory)
            ctx.lessons = bundle.lessons
            if bundle.lessons:
                self.ledger.append("capability", "context_assembled",
                                   rationale=f"{len(bundle.lessons)} lessons, "
                                             f"{bundle.dropped} dropped, {bundle.chars} chars",
                                   decision="INFO")
            result = self.cap.execute(item, ctx)
            report.cycles.append(result)

            # Reflect the capability's lessons into memory.
            for text, kind, tags in result.lessons:
                self.memory.remember(text, kind=kind, tags=tags, source=self.cap.name)

            self.ledger.append("capability", "decision",
                               rationale=f"{item[:60]} -> ok={result.ok} score={result.score}",
                               decision="PASS" if result.ok else "BLOCK",
                               data={"summary": result.summary[:400]})

            # Evolve the doctrine against the capability's benchmark.
            if evolve_every and idx % evolve_every == 0 and self.budget_left > 0:
                self._evolve(generations)
                report.evolutions += 1

            # Sleep: consolidate short-term lessons into long-term memory.
            if consolidate_every and idx % consolidate_every == 0:
                stats = self.memory.consolidate()
                report.consolidations += 1
                self.ledger.append("capability", "consolidate", rationale=str(stats)[:120],
                                   decision="INFO")

            if not backlog and keep_going and (max_cycles is None or idx < max_cycles):
                backlog = self.cap.plan(f"{objective} (continue)", ctx)

        self.memory.consolidate()
        after = self._adopt()  # `is None` check: a legitimate 0.0 score is falsy
        report.genome_score_after = after if after is not None else report.genome_score_before
        report.calls = self.metrics.calls
        report.lessons = len(self.memory)
        report.long_term_lessons = self.memory.stats()["long_term"]
        report.ledger_ok = self.ledger.verify()
        self.ledger.append("capability", "run_end",
                           rationale=f"decisions={len(report.cycles)} evolutions={report.evolutions}",
                           decision="INFO")
        return report

    def _evolve(self, generations: int) -> None:
        engine = EvolutionEngine(
            config=self.config, provider=self.provider, constitution=self.constitution,
            archive=self.archive, ledger=self.ledger, role=self.cap.evolve_role(),
            benchmark=self.cap.benchmark(self._ctx()), directive_pool=self.cap.directives(),
            param_space=self.cap.param_space(), metrics=self.metrics,
        )
        engine.evolve(generations=generations)
        best = self.archive.best_for(self.cap.evolve_role())
        if best:
            self.genomes[self.cap.evolve_role()] = best.to_genome()
            self.ledger.append("capability", "adopt_genome",
                               rationale=f"{self.cap.evolve_role()} score={best.score}",
                               decision="PASS")
