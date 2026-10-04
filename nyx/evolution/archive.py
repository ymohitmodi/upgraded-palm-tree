"""The evolution archive.

A persistent, tree-structured archive of agent genomes — the Darwin-Gödel idea:
keep *every* admitted variant (not just the current best) so evolution can
branch from older genomes and stay open-ended, escaping local optima.
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from ..agents.base import Genome


@dataclass
class GenomeRecord:
    id: str
    genome: dict          # serialized Genome
    score: float
    parent_id: str | None
    generation: int
    ts: float = field(default_factory=time.time)
    note: str = ""

    def to_genome(self) -> Genome:
        data = dict(self.genome)
        return Genome(**data)


class Archive:
    """Persisted collection of genome records with novelty-aware selection."""

    def __init__(self, path: str | Path = ".nyx/evolution_archive"):
        self.dir = Path(path)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.file = self.dir / "archive.jsonl"
        self.records: list[GenomeRecord] = self._load()

    def _load(self) -> list[GenomeRecord]:
        if not self.file.exists():
            return []
        out = []
        for line in self.file.read_text(encoding="utf-8").splitlines():
            if line.strip():
                out.append(GenomeRecord(**json.loads(line)))
        return out

    def add(self, record: GenomeRecord) -> None:
        self.records.append(record)
        with self.file.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(asdict(record), separators=(",", ":")) + "\n")

    def __len__(self) -> int:
        return len(self.records)

    def best(self) -> GenomeRecord | None:
        return max(self.records, key=lambda r: r.score) if self.records else None

    def best_for(self, role: str) -> GenomeRecord | None:
        """Highest-scoring admitted genome for a given role, if any."""
        candidates = [r for r in self.records if r.genome.get("role") == role]
        return max(candidates, key=lambda r: r.score) if candidates else None

    def select_parent(self, rng, role: str | None = None) -> GenomeRecord | None:
        """Pick a parent favoring high score, but with novelty: occasionally
        branch from a less-explored (fewer children) genome to stay open-ended.

        When ``role`` is given, selection is restricted to that role's genomes so
        evolving one role never mutates another role's lineage.
        """
        pool = (
            [r for r in self.records if r.genome.get("role") == role]
            if role is not None
            else list(self.records)
        )
        if not pool:
            return None
        child_counts = {r.id: 0 for r in pool}
        for r in pool:
            if r.parent_id in child_counts:
                child_counts[r.parent_id] += 1

        # Exploration branch: pick a rarely-extended genome.
        if rng.random() < 0.3:
            return min(pool, key=lambda r: child_counts[r.id])
        # Exploitation: weight by score.
        weights = [max(r.score, 0.01) for r in pool]
        total = sum(weights)
        pick = rng.random() * total
        acc = 0.0
        for r, w in zip(pool, weights):
            acc += w
            if pick <= acc:
                return r
        return pool[-1]

    def lineage(self, record_id: str) -> list[GenomeRecord]:
        by_id = {r.id: r for r in self.records}
        chain: list[GenomeRecord] = []
        cur = by_id.get(record_id)
        while cur is not None:
            chain.append(cur)
            cur = by_id.get(cur.parent_id) if cur.parent_id else None
        return list(reversed(chain))
