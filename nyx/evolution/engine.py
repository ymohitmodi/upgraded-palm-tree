"""The evolution loop — open-ended, empirical self-improvement.

Select a parent genome from the archive, mutate it, evaluate it on a benchmark,
and admit it **only if it beats its ancestor by a threshold** (Darwin-Gödel).
Mutations that would violate the Constitution are rejected before evaluation, so
agents evolve competence, never away from their values.
"""
from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass, field
from typing import Callable

from ..agents.base import Agent, Genome
from ..agents.roles import build_agent
from ..config import Config, load_config
from ..constitution import Constitution
from ..observability.ledger import AuditLedger
from ..observability.metrics import Metrics
from ..providers import build_provider
from ..providers.base import Provider
from ..security.guardrails import detect_injection, scan_secrets
from .archive import Archive, GenomeRecord

# Candidate charter directives the engine can graft onto a genome.
_DIRECTIVE_POOL = [
    "Always add precise input validation and type checks.",
    "Prefer small pure functions and explicit error handling.",
    "Add a docstring referencing the spec's acceptance criteria.",
    "Cover edge cases and write the failing test first.",
    "Keep secrets out of code and logs; never log raw input.",
    "Optimize for the next agent's readability; match conventions.",
]

Benchmark = Callable[[Agent], float]


@dataclass
class EvolutionReport:
    generations: int
    admitted: int
    rejected: int
    archive_size: int
    best_score_before: float
    best_score_after: float
    best_genome: dict = field(default_factory=dict)

    @property
    def gain(self) -> float:
        return round(self.best_score_after - self.best_score_before, 4)


def _genome_id(genome: Genome) -> str:
    # Params are part of the identity: a param-only mutation is a distinct genome
    # and must get its own archive id (else it collides with its parent).
    param_blob = ";".join(f"{k}={round(v, 4)}" for k, v in sorted(genome.params.items()))
    blob = (f"{genome.role}|{genome.system_prompt}|{genome.temperature}|"
            f"{genome.model_role}|{genome.max_tokens}|{param_blob}")
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:12]


class EvolutionEngine:
    def __init__(
        self,
        config: Config | None = None,
        provider: Provider | None = None,
        constitution: Constitution | None = None,
        archive: Archive | None = None,
        ledger: AuditLedger | None = None,
        role: str = "coder",
        benchmark: Benchmark | None = None,
        seed: int = 1234,
        metrics: Metrics | None = None,
        directive_pool: list[str] | None = None,
        param_space: dict | None = None,
    ):
        self.config = config or load_config()
        self.provider = provider or build_provider(self.config)
        self.constitution = constitution or Constitution.load(
            self.config.constitution_path, mode=self.config.constitution_mode
        )
        # NB: Archive defines __len__, so an empty one is falsy; use `is None`.
        self.archive = archive if archive is not None else Archive(self.config.evolution_archive)
        self.ledger = ledger or AuditLedger(self.config.ledger_path)
        self.role = role
        self.benchmark = benchmark or self._default_benchmark
        # The pool of charter directives mutation can graft on (domain-tunable).
        self.directive_pool = directive_pool or _DIRECTIVE_POOL
        # Continuous gene space {name: (lo, hi, default)} for roles whose fitness
        # reads numeric params (e.g. the value analyst). Empty = prompt-only role.
        self.param_space = dict(param_space or {})
        self.rng = random.Random(seed)
        # Shared metrics let a caller (e.g. a mission) account benchmark calls
        # against one budget; otherwise the engine keeps its own counter.
        self.metrics = metrics if metrics is not None else Metrics()

    # -- agent construction --------------------------------------------------
    def _agent_for(self, genome: Genome) -> Agent:
        agent = build_agent(
            self.role,
            self.config,
            self.provider,
            self.constitution,
            ledger=None,  # benchmarking is not a consequential action
            metrics=self.metrics,
            genome=genome,
        )
        return agent

    def _seed_genome(self) -> Genome:
        """Seed from the role's *production* charter so evolution searches for
        improvements above the baseline and adopted genomes never regress."""
        return build_agent(self.role, self.config, self.provider, self.constitution).genome

    # -- mutation ------------------------------------------------------------
    def mutate(self, genome: Genome) -> Genome:
        ops = ["temperature", "directive", "model_role", "directive", "max_tokens"]
        # Bias toward the continuous genes when the role has them — that is where a
        # quantitative fitness (the value backtest) actually moves, so spending
        # mutations there is what breaks the 4-weight plateau.
        if self.param_space:
            ops += ["param", "param", "param"]
        op = self.rng.choice(ops)
        if op == "temperature":
            delta = self.rng.choice([-0.1, 0.1, 0.15, -0.05])
            new_temp = min(0.95, max(0.0, round(genome.temperature + delta, 2)))
            child = genome.mutate(temperature=new_temp)
        elif op == "model_role":
            choices = ["coder", "architect", "reviewer", "fast"]
            child = genome.mutate(model_role=self.rng.choice(choices))
        elif op == "max_tokens":
            # Longer budgets let deliverable roles (advisor) finish structured,
            # specific reports the rubric rewards; bounded so cost stays sane.
            delta = self.rng.choice([-512, 512, 1024])
            child = genome.mutate(max_tokens=min(8192, max(512, genome.max_tokens + delta)))
        elif op == "param":
            child = self._mutate_param(genome)
        else:  # directive: append an improvement to the charter (never twice —
            # repeated grafts would just bloat the prompt / game keyword scoring)
            fresh = [d for d in self.directive_pool if d not in genome.system_prompt]
            if fresh:
                directive = self.rng.choice(fresh)
                sep = "" if genome.system_prompt.endswith("\n") else "\n"
                child = genome.mutate(system_prompt=genome.system_prompt + sep + directive)
            else:  # pool exhausted: fall back to a parameter tweak
                child = genome.mutate(temperature=min(0.95, round(genome.temperature + 0.05, 2)))
        child.lineage = list(genome.lineage) + [_genome_id(genome)]
        return child

    def _mutate_param(self, genome: Genome) -> Genome:
        """Perturb the continuous genes. An unparameterized genome is first seeded
        from the role's whole param space (jittered defaults) so evolution gains
        every dimension at once; thereafter one dimension is nudged within bounds."""
        params = dict(genome.params)
        if not params:
            for name, (lo, hi, default) in self.param_space.items():
                jitter = self.rng.uniform(-0.1, 0.1) * (hi - lo)
                params[name] = round(min(hi, max(lo, default + jitter)), 4)
        else:
            name = self.rng.choice(list(params))
            lo, hi, _ = self.param_space.get(
                name, (params[name] * 0.5, params[name] * 1.5 or 1.0, params[name]))
            step = self.rng.uniform(-0.25, 0.25) * (hi - lo)
            params[name] = round(min(hi, max(lo, params[name] + step)), 4)
        return genome.mutate(params=params)

    def _constitutional(self, genome: Genome) -> bool:
        """Reject mutations that try to weaken governance."""
        if detect_injection(genome.system_prompt):
            return False
        if scan_secrets(genome.system_prompt):
            return False
        return True

    # -- benchmark -----------------------------------------------------------
    def _default_benchmark(self, agent: Agent) -> float:
        """Default fitness. For the coder role this is **executed** correctness:
        the agent's code is run against hidden tests in the sandbox (real signal,
        no keyword theater). Non-executable roles (reviewer, planner, …) fall back
        to charter/doctrine quality, which is the only signal they have. A small
        genome-quality term breaks ties without letting keywords dominate.
        """
        if self.role == "coder":
            from .benchmarks import default_swebench_suite

            executed = default_swebench_suite()(agent)          # fraction of tests passing
            genome = self._genome_quality(agent.genome)
            return round(0.85 * executed + 0.15 * genome, 4)    # reality dominates

        # Non-coder roles: score the charter's doctrine + sane temperature.
        return self._genome_quality(agent.genome)

    @staticmethod
    def _genome_quality(genome: Genome) -> float:
        """Reward a charter that explicitly encodes the doctrine + sane params."""
        low = genome.system_prompt.lower()
        keywords = ["valid", "test", "readab", "pure", "secret", "edge", "docstring", "convention"]
        hits = sum(1 for k in keywords if k in low)
        doctrine = min(hits / 5.0, 1.0)              # saturates at 5 doctrines
        temp_fit = 1.0 - min(abs(genome.temperature - 0.3) / 0.6, 1.0)
        return round(0.75 * doctrine + 0.25 * temp_fit, 4)

    # -- evolution loop ------------------------------------------------------
    def evolve(self, generations: int = 5) -> EvolutionReport:
        # Seed when *this role* has no genome yet (not merely when the whole
        # archive is empty), so evolving a new role on a shared archive works.
        if self.archive.best_for(self.role) is None:
            seed_genome = self._seed_genome()
            score = self.benchmark(self._agent_for(seed_genome))
            rec = GenomeRecord(
                id=_genome_id(seed_genome),
                genome=_serialize(seed_genome),
                score=score,
                parent_id=None,
                generation=0,
                note="seed",
            )
            self.archive.add(rec)
            self.ledger.append(
                "evolution", "seed_archive", rationale=f"role={self.role} score={score}", decision="INFO"
            )

        before = self.archive.best_for(self.role).score
        admitted = rejected = 0

        for gen in range(1, generations + 1):
            # Role-scoped selection: only mutate this role's lineage.
            parent = self.archive.select_parent(self.rng, role=self.role)
            child_genome = self.mutate(parent.to_genome())

            if not self._constitutional(child_genome):
                rejected += 1
                self.ledger.append(
                    "evolution", "reject_unconstitutional", rationale=f"gen={gen}", decision="BLOCK"
                )
                continue

            child_score = self.benchmark(self._agent_for(child_genome))
            improvement = child_score - parent.score

            if improvement > self.config.evolution_threshold:
                rec = GenomeRecord(
                    id=_genome_id(child_genome),
                    genome=_serialize(child_genome),
                    score=child_score,
                    parent_id=parent.id,
                    generation=gen,
                    note=f"+{improvement:.3f} over parent",
                )
                self.archive.add(rec)
                admitted += 1
                self.ledger.append(
                    "evolution",
                    "admit_genome",
                    rationale=f"gen={gen} score={child_score} gain={improvement:.3f}",
                    decision="PASS",
                    data={"id": rec.id, "parent": parent.id},
                )
            else:
                rejected += 1
                self.ledger.append(
                    "evolution",
                    "reject_no_gain",
                    rationale=f"gen={gen} score={child_score} parent={parent.score}",
                    decision="INFO",
                )

        best = self.archive.best_for(self.role)
        return EvolutionReport(
            generations=generations,
            admitted=admitted,
            rejected=rejected,
            archive_size=len(self.archive),
            best_score_before=before,
            best_score_after=best.score,
            best_genome=best.genome,
        )

    # -- constitution amendment (optional, ratchet-guarded) ------------------
    def propose_amendment(self, new_constitution_data: dict) -> bool:
        """Attempt a constitution amendment; admitted only if it doesn't weaken
        any immutable principle (the values ratchet)."""
        verdict = self.constitution.validate_amendment(new_constitution_data)
        self.ledger.append(
            "evolution",
            "propose_amendment",
            rationale=verdict.rationale,
            decision="PASS" if verdict.passed else "BLOCK",
        )
        return verdict.passed


def _serialize(genome: Genome) -> dict:
    return {
        "role": genome.role,
        "system_prompt": genome.system_prompt,
        "model_role": genome.model_role,
        "temperature": genome.temperature,
        "top_p": genome.top_p,
        "max_tokens": genome.max_tokens,
        "tools": list(genome.tools),
        "lineage": list(genome.lineage),
        "params": dict(genome.params),
    }
