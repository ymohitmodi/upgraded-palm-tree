"""Memory & continual learning — how NYX *remembers* and gets wiser.

NYX learns on three distinct substrates. Two already exist elsewhere in the
codebase; this module adds the third and ties them together:

  1. EPISODIC  — the audit ledger (observability/ledger.py). The immutable,
     hash-chained record of *what happened*: every action, gate, and rationale.
     This is perfect recall of events, but raw and unsummarized.

  2. PROCEDURAL — the evolution archive (evolution/archive.py). Learned *skills*:
     improved agent genomes (prompts, tools, params) admitted only when they beat
     their ancestor. This is "getting better at the job", banked durably.

  3. SEMANTIC  — this module. Distilled, reusable *lessons* ("for billing
     features, validate currency precision"; "this objective tends to fail the
     security gate on secret handling"). Lessons are recalled by relevance and
     injected into agent prompts on later runs, so the factory applies what it
     learned without retraining anything.

The flywheel:  execute → REFLECT (distill lessons from outcomes) → REMEMBER →
RECALL on the next task → better execution. Combined with evolution (procedural)
and the ledger (episodic), the factory compounds knowledge over time on a single
mini-PC, fully offline, with no embeddings or external store.
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

_STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "from", "into", "your", "our",
    "are", "was", "were", "will", "add", "build", "ship", "make", "use", "via",
    "feature", "features", "objective", "milestone", "continue", "improving",
}


def _tokens(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) >= 3 and w not in _STOPWORDS}


@dataclass
class Lesson:
    id: str
    text: str
    kind: str = "lesson"          # lesson | pattern | preference | risk
    tags: list[str] = field(default_factory=list)
    source: str = ""
    weight: float = 1.0           # reinforced when re-learned, decays when stale
    uses: int = 0                 # times recalled/applied
    ts: float = field(default_factory=time.time)

    def tokenset(self) -> set[str]:
        return _tokens(self.text) | {t.lower() for t in self.tags}


def _lesson_id(text: str, kind: str) -> str:
    import hashlib

    return hashlib.sha256(f"{kind}:{text.strip().lower()}".encode()).hexdigest()[:12]


class MemoryStore:
    """Persistent semantic memory of distilled lessons (JSONL, dependency-free)."""

    def __init__(self, path: str | Path = ".nyx/memory.jsonl"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lessons: dict[str, Lesson] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                data = json.loads(line)
                self.lessons[data["id"]] = Lesson(**data)

    def _flush(self) -> None:
        with self.path.open("w", encoding="utf-8") as fh:
            for lesson in self.lessons.values():
                fh.write(json.dumps(asdict(lesson), separators=(",", ":")) + "\n")

    def remember(
        self,
        text: str,
        *,
        kind: str = "lesson",
        tags: list[str] | None = None,
        source: str = "",
        weight: float = 1.0,
    ) -> Lesson:
        """Store a lesson; if already known, reinforce it instead of duplicating."""
        text = text.strip()
        lid = _lesson_id(text, kind)
        existing = self.lessons.get(lid)
        if existing:
            existing.weight = round(existing.weight + weight * 0.5, 3)
            existing.ts = time.time()
            if tags:
                existing.tags = sorted(set(existing.tags) | set(tags))
        else:
            self.lessons[lid] = Lesson(
                id=lid, text=text, kind=kind, tags=tags or [], source=source, weight=weight
            )
        self._flush()
        return self.lessons[lid]

    def recall(self, query: str, k: int = 5, kind: str | None = None) -> list[Lesson]:
        """Return the k most relevant lessons for a query (keyword overlap × weight)."""
        q = _tokens(query)
        if not q:
            return []
        scored: list[tuple[float, Lesson]] = []
        for lesson in self.lessons.values():
            if kind and lesson.kind != kind:
                continue
            overlap = q & lesson.tokenset()
            if not overlap:
                continue
            # Jaccard-ish relevance, boosted by reinforcement weight.
            rel = len(overlap) / len(q | lesson.tokenset())
            scored.append((rel * lesson.weight, lesson))
        scored.sort(key=lambda x: x[0], reverse=True)
        top = [lesson for _, lesson in scored[:k]]
        for lesson in top:
            lesson.uses += 1
        if top:
            self._flush()
        return top

    def __len__(self) -> int:
        return len(self.lessons)

    def all(self) -> list[Lesson]:
        return sorted(self.lessons.values(), key=lambda x: x.weight, reverse=True)


def reflect_on_run(result, store: MemoryStore) -> list[Lesson]:
    """Distill durable lessons from a finished FactoryResult.

    Failures become guardrail lessons, security findings become risk lessons, and
    a clean ship reinforces the pattern that worked — all tagged with words from
    the intent so they resurface on similar future work.
    """
    learned: list[Lesson] = []
    intent_tags = sorted(_tokens(result.intent))[:6]

    for stage in result.stages:
        if not stage.passed and stage.gate:
            learned.append(
                store.remember(
                    f"For work like '{result.intent}', satisfy {stage.gate} early: "
                    f"{stage.rationale.split('BLOCK:')[-1].strip()}",
                    kind="lesson",
                    tags=intent_tags + [stage.stage, stage.gate],
                    source=f"run:{stage.stage}",
                    weight=1.5,
                )
            )

    # Guardrail findings surfaced during the run become risk lessons.
    for finding in getattr(result, "findings", []) or []:
        learned.append(
            store.remember(
                f"Security watch: {finding}", kind="risk",
                tags=intent_tags + ["security"], source="guardrails", weight=1.2,
            )
        )

    if result.shipped:
        learned.append(
            store.remember(
                f"Pattern that shipped cleanly: gated pipeline for '{result.intent}' "
                "(spec → fan-out build → security co-sign → tests → reversible deploy).",
                kind="pattern", tags=intent_tags, source="run:shipped", weight=0.8,
            )
        )
    return learned
