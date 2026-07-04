"""The original software dark-factory, expressed as a Capability.

This makes the point that the factory is just one capability among many: the same
runner that drives the value investor drives software delivery.
"""
from __future__ import annotations

import re

from ..agents.roles import build_agent
from ..factory.orchestrator import Factory
from .base import Capability, CycleContext, CycleResult, EvalResult


class SoftwareFactoryCapability(Capability):
    name = "software"
    description = "Build & ship software through the gated SDLC pipeline."

    def matches(self, objective: str) -> bool:
        return True  # the catch-all default

    def evolve_role(self) -> str:
        return "coder"

    def plan(self, objective: str, ctx: CycleContext) -> list[str]:
        planner = build_agent("planner", ctx.config, ctx.provider, ctx.constitution,
                              ledger=ctx.ledger, metrics=ctx.metrics)
        items = []
        for line in planner.run(objective).text.splitlines():
            m = re.match(r"\s*[-*]\s+(.*)", line)
            if m and m.group(1).strip():
                items.append(m.group(1).strip())
        return items or [f"{objective} — milestone {i + 1}" for i in range(3)]

    def seed_memory(self, memory) -> int:
        """Seed the solopreneur business doctrine so the factory prioritizes
        like a successful one-person company, not just an engineering pipeline."""
        from ..domains.solopreneur import seed_principles

        return seed_principles(memory)

    def eval(self, config, provider) -> EvalResult:
        from ..constitution import Constitution
        from ..evolution.archive import Archive
        from ..evolution.benchmarks import heldout_swebench_suite
        from ..observability.metrics import Metrics

        best = Archive(config.evolution_archive).best_for("coder")
        genome = best.to_genome() if best else None
        const = Constitution.load(config.constitution_path, mode=config.constitution_mode)
        agent = build_agent("coder", config, provider, const, metrics=Metrics(), genome=genome)
        score = heldout_swebench_suite()(agent)
        return EvalResult(score=score,
                          detail=f"held-out SWE-bench, {'evolved' if best else 'seed'} coder")

    def execute(self, task: str, ctx: CycleContext) -> CycleResult:
        factory = Factory(config=ctx.config, provider=ctx.provider,
                          constitution=ctx.constitution, ledger=ctx.ledger,
                          metrics=ctx.metrics, genomes=ctx.genomes, memory=ctx.memory)
        r = factory.build(task, approver=lambda *_: ctx.config.autonomy == "autonomous")
        return CycleResult(
            item=task, ok=r.shipped or r.held_for_approval, blocked_at=r.blocked_at,
            summary=f"shipped={r.shipped} held={r.held_for_approval}",
            score=factory.metrics.gate_pass_rate, findings=r.findings,
        )
