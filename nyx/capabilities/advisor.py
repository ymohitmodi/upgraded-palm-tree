"""AdvisorCapability — LLM-driven pursuit of ambiguous personal/business goals.

No rule-based logic in the work itself: the planner agent decomposes the
objective, the Advisor agent produces a concrete deliverable per task (plan,
draft, checklist, research memo), the constitution gates it, and reflection
writes what was learned back to memory. Handles goals like "grow my senior SDE
career" or "get EB-1 publications ready" out of the box.
"""
from __future__ import annotations

import re

from ..agents.roles import build_agent
from .base import Capability, CycleContext, CycleResult

_MATCH = re.compile(
    r"\b(career|promot|eb-?1|visa|immigra|publicat|resume|interview|mentor|"
    r"brand|grow|strateg|advis|coach|plan my|goal)", re.IGNORECASE)


class AdvisorCapability(Capability):
    name = "advisor"
    description = ("Pursue ambiguous personal/professional goals (career growth, EB-1 "
                   "evidence, research agendas) with concrete gated deliverables.")

    def matches(self, objective: str) -> bool:
        return bool(_MATCH.search(objective))

    def allowed_tools(self) -> set[str]:
        return {"web_fetch", "web_crawl", "read_url"}  # research only — no financial creds

    def evolve_role(self) -> str:
        return "advisor"

    def seed_memory(self, memory) -> int:
        from ..domains.career import seed_principles

        return seed_principles(memory)

    def plan(self, objective: str, ctx: CycleContext) -> list[str]:
        planner = build_agent("planner", ctx.config, ctx.provider, ctx.constitution,
                              ledger=ctx.ledger, metrics=ctx.metrics)
        items = [m.group(1).strip()
                 for line in planner.run(objective).text.splitlines()
                 if (m := re.match(r"\s*[-*]\s+(.*)", line))]
        return items[:6] or [f"{objective} — milestone {i + 1}" for i in range(3)]

    def execute(self, task: str, ctx: CycleContext) -> CycleResult:
        agent = build_agent("advisor", ctx.config, ctx.provider, ctx.constitution,
                            ledger=ctx.ledger, metrics=ctx.metrics,
                            genome=ctx.genomes.get("advisor"))
        agent.lessons = ctx.lessons  # recalled doctrine + past learnings
        # Agentic: the advisor may call research tools (web_fetch/read_url) to
        # ground its deliverable; degrades to single-shot when the brain can't.
        result = agent.run_with_tools(task, ctx.toolbox)
        verdict = ctx.constitution.evaluate("review", result.text, {"security_ok": True})
        lessons = [(f"Advisor deliverable for '{task[:60]}' "
                    f"{'passed' if verdict.passed else 'was blocked by'} gates.",
                    "lesson", ["advisor"] + sorted(task.lower().split()[:3]))]
        return CycleResult(
            item=task, ok=verdict.passed, summary=result.text,
            blocked_at=None if verdict.passed else verdict.gate,
            findings=list(verdict.violations), lessons=lessons,
        )
