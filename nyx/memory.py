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
    kind: str = "lesson"          # lesson | pattern | preference | risk | principle
    tags: list[str] = field(default_factory=list)
    source: str = ""
    weight: float = 1.0           # reinforced when re-learned, decays when stale
    uses: int = 0                 # times recalled/applied
    tier: str = "short_term"      # short_term -> consolidated into long_term
    ts: float = field(default_factory=time.time)        # first learned
    last_used: float = field(default_factory=time.time)  # last reinforced/recalled

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
            existing.last_used = time.time()
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
            # Jaccard-ish relevance, boosted by reinforcement weight, with a
            # preference for consolidated long-term memories (more general/proven).
            rel = len(overlap) / len(q | lesson.tokenset())
            tier_boost = 1.5 if lesson.tier == "long_term" else 1.0
            scored.append((rel * lesson.weight * tier_boost, lesson))
        scored.sort(key=lambda x: x[0], reverse=True)
        top = [lesson for _, lesson in scored[:k]]
        now = time.time()
        for lesson in top:
            lesson.uses += 1
            lesson.last_used = now
        if top:
            self._flush()
        return top

    def __len__(self) -> int:
        return len(self.lessons)

    def all(self) -> list[Lesson]:
        return sorted(self.lessons.values(), key=lambda x: x.weight, reverse=True)

    def stats(self) -> dict:
        long_term = sum(1 for x in self.lessons.values() if x.tier == "long_term")
        return {"total": len(self.lessons), "long_term": long_term,
                "short_term": len(self.lessons) - long_term}

    # -- consolidation ("sleep"): form long-term memory ---------------------
    _GENERIC_TAGS = {"core", "flow", "page", "data", "model", "errors"}

    def consolidate(
        self,
        *,
        now: float | None = None,
        half_life_days: float = 7.0,
        min_weight: float = 0.2,
        cluster_min: int = 3,
        promote_uses: int = 3,
    ) -> dict:
        """A brain-like consolidation pass — run periodically, like sleep.

        1. DECAY    short-term lessons by recency (Ebbinghaus forgetting curve).
        2. ABSTRACT recurring short-term lessons that share a theme (tag) into a
           single, stronger LONG-TERM principle (hippocampus → neocortex).
        3. PROMOTE  frequently-applied lessons straight to long-term.
        4. FORGET   short-term lessons whose weight has decayed below the floor.

        Long-term memories don't decay and are preferred at recall time.
        """
        now = now or time.time()
        decayed = promoted = consolidated = forgotten = 0

        # 1. Decay short-term memories by how long since they were last used.
        for lesson in self.lessons.values():
            if lesson.tier == "long_term":
                continue
            age_days = max(0.0, (now - lesson.last_used) / 86400.0)
            if age_days > 0:
                lesson.weight = round(lesson.weight * (0.5 ** (age_days / half_life_days)), 4)
                decayed += 1

        # 2. Abstract recurring themes (shared, non-generic tag) into principles.
        theme_members: dict[str, list[Lesson]] = {}
        for lesson in self.lessons.values():
            if lesson.tier == "long_term":
                continue
            for tag in lesson.tags:
                t = tag.lower()
                if t in self._GENERIC_TAGS or t in _STOPWORDS:
                    continue
                theme_members.setdefault(t, []).append(lesson)

        absorbed: set[str] = set()
        for theme, members in theme_members.items():
            # A lesson joins at most ONE principle per pass (multi-tag lessons
            # must not be double-counted into several themes).
            members = [m for m in members if m.id not in absorbed]
            if len(members) < cluster_min:
                continue
            members.sort(key=lambda x: x.weight, reverse=True)
            representative = members[0].text
            text = f"[{theme}] recurring across {len(members)} runs — {representative}"
            lid = _lesson_id(text, "principle")
            self.lessons[lid] = Lesson(
                id=lid, text=text, kind="principle", tags=[theme],
                source="consolidation", tier="long_term",
                weight=round(sum(m.weight for m in members), 3),
                uses=sum(m.uses for m in members), last_used=now,
            )
            consolidated += 1
            # Absorb the specifics: keep the records (they may still be recalled
            # individually) but fade them so the principle dominates; unused ones
            # are forgotten by later decay instead of being hard-deleted.
            for m in members:
                absorbed.add(m.id)
                m.weight = round(m.weight * 0.4, 4)

        # 3. Promote heavily-used short-term lessons to long-term.
        for lesson in self.lessons.values():
            if lesson.tier != "long_term" and lesson.uses >= promote_uses:
                lesson.tier = "long_term"
                promoted += 1

        # 4. Forget faded short-term memories.
        for lid in [x.id for x in self.lessons.values()
                    if x.tier != "long_term" and x.weight < min_weight]:
            self.lessons.pop(lid, None)
            forgotten += 1

        self._flush()
        return {"decayed": decayed, "consolidated": consolidated,
                "promoted": promoted, "forgotten": forgotten, **self.stats()}


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
