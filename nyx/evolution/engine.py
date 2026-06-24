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
    blob = f"{genome.role}|{genome.system_prompt}|{genome.temperature}|{genome.model_role}"
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
        op = self.rng.choice(["temperature", "directive", "model_role", "directive"])
        if op == "temperature":
            delta = self.rng.choice([-0.1, 0.1, 0.15, -0.05])
            new_temp = min(0.95, max(0.0, round(genome.temperature + delta, 2)))
            child = genome.mutate(temperature=new_temp)
        elif op == "model_role":
            choices = ["coder", "architect", "reviewer", "fast"]
            child = genome.mutate(model_role=self.rng.choice(choices))
        else:  # directive: append an improvement to the charter
            directive = self.rng.choice(_DIRECTIVE_POOL)
            sep = "" if genome.system_prompt.endswith("\n") else "\n"
            child = genome.mutate(system_prompt=genome.system_prompt + sep + directive)
        child.lineage = list(genome.lineage) + [_genome_id(genome)]
        return child

    def _constitutional(self, genome: Genome) -> bool:
        """Reject mutations that try to weaken governance."""
        if detect_injection(genome.system_prompt):
            return False
        if scan_secrets(genome.system_prompt):
            return False
        return True

    # -- benchmark -----------------------------------------------------------
    def _default_benchmark(self, agent: Agent) -> float:
        """Reference benchmark: score a genome on a small suite.

        Combines (a) how the produced *artifact* looks and (b) how well the
        genome's *charter* encodes the engineering doctrine and uses a sensible
        temperature. Replace this with SWE-bench-style tasks or your product
        KPIs for a live factory; the admission mechanics are identical.
        """
        tasks = [
            "sum a list of numbers safely",
            "validate and parse a numeric config",
            "compute a moving average over a window",
        ]
        artifact_scores = []
        for t in tasks:
            text = agent.run(t).text
            low = text.lower()
            s = 0.0
            s += 0.30 if ("valid" in low or "raise" in low) else 0.0
            s += 0.25 if "```" in text else 0.0
            s += 0.20 if "def " in text else 0.0
            s += 0.15 if not scan_secrets(text) else 0.0
            s += 0.10 if not self.constitution.check_forbidden(text) else 0.0
            artifact_scores.append(s)
        artifact = sum(artifact_scores) / len(artifact_scores)
        genome = self._genome_quality(agent.genome)
        # Mock artifacts are constant, so the genome term carries the gradient;
        # with a real brain the artifact term dominates instead.
        return round(0.3 * artifact + 0.7 * genome, 4)

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
    }
