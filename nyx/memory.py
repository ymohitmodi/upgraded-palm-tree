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
    trusted: bool = True          # False for externally-sourced content (anti-poisoning)
    ts: float = field(default_factory=time.time)        # first learned
    last_used: float = field(default_factory=time.time)  # last reinforced/recalled

    def tokenset(self) -> set[str]:
        return _tokens(self.text) | {t.lower() for t in self.tags}


def _lesson_id(text: str, kind: str) -> str:
    import hashlib

    return hashlib.sha256(f"{kind}:{text.strip().lower()}".encode()).hexdigest()[:12]


class MemoryStore:
    """Persistent semantic memory of distilled lessons (JSONL, dependency-free)."""

    def __init__(self, path: str | Path = ".nyx/memory.jsonl", embedder=None):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lessons: dict[str, Lesson] = {}
        # Vector recall: default to the offline hashing embedder; inject a
        # ProviderEmbedder for true semantic similarity when a brain is live.
        if embedder is None:
            from .embeddings import default_embedder
            embedder = default_embedder()
        self.embedder = embedder
        self._vecs: dict[str, list[float]] = {}   # lesson id -> cached vector
        self._load()

    def _vector(self, lesson: Lesson) -> list[float]:
        vec = self._vecs.get(lesson.id)
        if vec is None:
            try:
                vec = self.embedder.embed(f"{lesson.text} {' '.join(lesson.tags)}")
            except Exception:  # noqa: BLE001 — embedding must never break recall
                vec = []
            self._vecs[lesson.id] = vec
        return vec

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
        trusted: bool = True,
    ) -> Lesson:
        """Store a lesson; if already known, reinforce it instead of duplicating.

        ``trusted=False`` marks externally-sourced content (fetched pages, filings,
        tickets). Untrusted memories are capped short-term and never form long-term
        doctrine, so poisoned external text cannot become a governing principle
        (OWASP Agentic T1 memory poisoning / LLM04)."""
        text = text.strip()
        lid = _lesson_id(text, kind)
        existing = self.lessons.get(lid)
        if existing:
            existing.weight = round(existing.weight + weight * 0.5, 3)
            existing.last_used = time.time()
            existing.trusted = existing.trusted or trusted  # a trusted source can vouch
            if tags:
                existing.tags = sorted(set(existing.tags) | set(tags))
        else:
            self.lessons[lid] = Lesson(
                id=lid, text=text, kind=kind, tags=tags or [], source=source,
                weight=weight, trusted=trusted,
            )
        self._vecs.pop(lid, None)  # invalidate cached vector on write
        self._flush()
        return self.lessons[lid]

    def learn_principle(self, text: str, *, tags: list[str] | None = None, source: str = "",
                        weight: float = 1.8, threshold: float = 0.86) -> tuple[Lesson, bool]:
        """Form durable doctrine from an authoritative, injection-screened insight
        — the way a careful reader adds to permanent notes.

        Dedup-aware: if a near-identical long-term principle already exists, REINFORCE
        it (a lesson repeated across decades of letters should get *stronger*, not
        duplicated); otherwise admit a new long-term principle. Returns (lesson,
        is_new). Unlike :meth:`remember`, this promotes straight to long-term — so
        reading the primary sources actually accumulates wisdom instead of decaying."""
        text = text.strip()
        if len(text) < 20:
            return self.remember(text, kind="principle", tags=tags, source=source), False
        for lesson, rel, _ in self.recall_scored(text, k=3, kind="principle", touch=False):
            if rel >= threshold and lesson.tier == "long_term":
                lesson.weight = round(lesson.weight + 0.6, 3)
                lesson.uses += 1
                lesson.last_used = time.time()
                if tags:
                    lesson.tags = sorted(set(lesson.tags) | set(tags))
                self._flush()
                return lesson, False
        lesson = self.remember(text, kind="principle", tags=tags, source=source,
                               weight=weight, trusted=True)
        lesson.tier = "long_term"     # authoritative doctrine is durable from the start
        self._flush()
        return lesson, True

    def recall(self, query: str, k: int = 5, kind: str | None = None) -> list[Lesson]:
        """Return the k most relevant lessons for a query.

        Relevance = cosine similarity in embedding space (semantic), blended with
        a smaller keyword-overlap term (exact-match precision), then boosted by
        reinforcement weight and a long-term-memory preference. Falls back to pure
        keyword overlap if embedding is unavailable.
        """
        return [lesson for lesson, _rel, _score in self.recall_scored(query, k=k, kind=kind)]

    def attach_doctrine(self, *stores: "MemoryStore") -> None:
        """Federate other capabilities' stores for cross-domain doctrine recall.

        With per-capability memory, the investor's Buffett principles and the
        advisor's career doctrine live in separate files. Attaching them here lets
        :meth:`recall_doctrine` surface durable, trusted principles from ALL of
        them — so Buffett's compounding lens can inform an EB-1A research agenda,
        and a research-rigor lesson can sharpen a stock memo — without merging the
        noisy per-domain research."""
        self._doctrine_stores = [s for s in stores if s is not self]

    def recall_doctrine(self, query: str, k: int = 4) -> list[Lesson]:
        """Cross-store recall of durable, TRUSTED principles only (never noisy or
        untrusted research). Pulls from this store plus any attached via
        :meth:`attach_doctrine`, deduped, best-first."""
        pool = [self, *getattr(self, "_doctrine_stores", [])]
        seen: dict[str, tuple[float, Lesson]] = {}
        for store in pool:
            for lesson, rel, _score in store.recall_scored(query, k=k * 2, touch=False):
                if lesson.trusted and lesson.tier == "long_term" and rel > 0.0:
                    prev = seen.get(lesson.id)
                    if prev is None or rel > prev[0]:
                        seen[lesson.id] = (rel * lesson.weight, lesson)
        return [ln for _, ln in sorted(seen.values(), key=lambda x: x[0], reverse=True)[:k]]

    def recall_scored(self, query: str, k: int = 5, kind: str | None = None,
                      *, touch: bool = True) -> list[tuple[Lesson, float, float]]:
        """Like :meth:`recall` but returns ``(lesson, relevance, score)`` triples.

        ``relevance`` is the raw 0..1 similarity (usable as a quality floor);
        ``score`` folds in weight/tier/trust for ranking. Set ``touch=False`` to
        score without recording a use (e.g. when assembling/inspecting context)."""
        from .embeddings import cosine

        q = _tokens(query)
        if not q:
            return []
        try:
            qvec = self.embedder.embed(query)
        except Exception:  # noqa: BLE001
            qvec = []
        scored: list[tuple[float, float, Lesson]] = []
        for lesson in self.lessons.values():
            if kind and lesson.kind != kind:
                continue
            overlap = q & lesson.tokenset()
            sim = cosine(qvec, self._vector(lesson)) if qvec else 0.0
            if sim <= 0.0 and not overlap:
                continue
            lexical = len(overlap) / len(q | lesson.tokenset()) if overlap else 0.0
            rel = 0.7 * sim + 0.3 * lexical if qvec else lexical
            tier_boost = 1.5 if lesson.tier == "long_term" else 1.0
            trust_boost = 1.0 if lesson.trusted else 0.6   # curated doctrine ranks first
            scored.append((rel * lesson.weight * tier_boost * trust_boost, rel, lesson))
        scored.sort(key=lambda x: x[0], reverse=True)
        top = scored[:k]
        if touch and top:
            now = time.time()
            for _score, _rel, lesson in top:
                lesson.uses += 1
                lesson.last_used = now
            self._flush()
        return [(lesson, rel, score) for score, rel, lesson in top]

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
    # Only these kinds are wisdom that can be abstracted into durable doctrine.
    # Bookkeeping kinds (track-record, meta) and raw research digests are recalled
    # for context but never elevated to a governing principle.
    _DOCTRINE_KINDS = {"principle", "lesson", "insight", "pattern"}

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
        #    ONLY trusted, doctrine-bearing lessons form principles — untrusted
        #    external content can't (anti-poisoning), and neither can bookkeeping
        #    (track-record/screen logs), which were polluting doctrine with lines
        #    like "top picks today: TCOM, ATAT" masquerading as a principle.
        theme_members: dict[str, list[Lesson]] = {}
        for lesson in self.lessons.values():
            if lesson.tier == "long_term" or not lesson.trusted:
                continue
            if lesson.kind not in self._DOCTRINE_KINDS:
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

        # 3. Promote heavily-used short-term lessons to long-term — trusted only.
        for lesson in self.lessons.values():
            if lesson.tier != "long_term" and lesson.trusted and lesson.uses >= promote_uses:
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
        # Outer feedback loop: this pattern shipped through gates that were
        # verified against REALITY (tests executed, code scanned) — not
        # self-graded — so it is a trustworthy positive signal to reinforce.
        learned.append(
            store.remember(
                f"TRACK RECORD — shipped '{result.intent}': passed execution-verified "
                "tests and scanned security through the gated pipeline.",
                kind="track-record", tags=intent_tags + ["shipped", "verified"],
                source="run:shipped", weight=0.9,
            )
        )
    return learned
