"""The Fan-Out Factory pattern.

For a given stage, run N diversified clones of an agent in parallel, then let a
judge (the constitutional Reviewer) pick the best candidate. This is how a solo
operator buys team-scale quality with cheap parallel compute: many attempts, one
winner.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from ..agents.base import Agent, AgentResult


@dataclass
class FanOutResult:
    winner: AgentResult
    candidates: list[AgentResult] = field(default_factory=list)
    selection_rationale: str = ""


def _diversify(base: Agent, n: int) -> list[Agent]:
    """Create n clones with diversified temperatures (and alternating model role)."""
    agents: list[Agent] = []
    for i in range(max(1, n)):
        temp = round(0.15 + 0.2 * i, 2)
        genome = base.genome.mutate(temperature=min(temp, 0.95))
        agents.append(base.clone_with(genome))
    return agents


class FanOut:
    """Run a stage as a parallel swarm and select the best result."""

    def __init__(self, judge: Agent | None = None, max_workers: int = 4):
        self.judge = judge
        self.max_workers = max_workers

    def run(self, base_agent: Agent, task: str, context: str, n: int) -> FanOutResult:
        agents = _diversify(base_agent, n)
        candidates: list[AgentResult] = []

        if len(agents) == 1:
            candidates = [agents[0].run(task, context)]
        else:
            with ThreadPoolExecutor(max_workers=min(self.max_workers, len(agents))) as pool:
                futures = [pool.submit(a.run, task, context) for a in agents]
                candidates = [f.result() for f in futures]

        base_agent.metrics.candidates_generated += len(candidates)
        winner, rationale = self._select(candidates, task)
        return FanOutResult(winner=winner, candidates=candidates, selection_rationale=rationale)

    def _select(self, candidates: list[AgentResult], task: str) -> tuple[AgentResult, str]:
        if len(candidates) == 1:
            return candidates[0], "single candidate"

        # If a candidate already carries a self-reported score, prefer those.
        scored = [c for c in candidates if c.score is not None]
        if scored:
            best = max(scored, key=lambda c: c.score or 0.0)
            return best, f"highest self-score {best.score}"

        # Otherwise ask the judge to score each candidate, lowest temperature wins ties.
        if self.judge is not None:
            best, best_score = candidates[0], -1.0
            for cand in candidates:
                verdict = self.judge.run(
                    f"Score this candidate for: {task}", context=cand.text
                )
                s = verdict.score if verdict.score is not None else 0.0
                if s > best_score:
                    best, best_score = cand, s
            return best, f"judge-selected score {best_score:.2f}"

        # Fallback heuristic: longest non-trivial artifact.
        best = max(candidates, key=lambda c: len(c.text))
        return best, "heuristic: most complete artifact"
