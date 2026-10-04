"""Context broker — assemble exactly the internal context a goal needs.

Two failure modes to avoid when feeding an agent:

1. **Missing context** — a single query misses relevant knowledge the goal
   implies. The broker probes the goal *and* its key sub-phrases, so it
   *discovers* the memories/lessons/skills that actually bear on the goal.
2. **Context pollution** — dumping many low-signal, tiny, or duplicate snippets
   makes the model *worse*. The broker enforces a relevance floor, de-duplicates,
   drops trivially short low-signal items, and caps the total by a character
   budget. Only high-signal, non-redundant context reaches the agent.

The result is a small, ranked, on-topic bundle — the useful minimum, not the
noisy maximum.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

_SPLIT = re.compile(r"[,.;:]| and | or | with | for | to ", re.IGNORECASE)
_WORD = re.compile(r"[a-z0-9][a-z0-9\-]{2,}", re.IGNORECASE)


@dataclass
class ContextBundle:
    lessons: list[str] = field(default_factory=list)   # ready to inject
    items: list = field(default_factory=list)          # (Lesson, relevance) for observability
    considered: int = 0
    dropped: int = 0
    chars: int = 0


class ContextBroker:
    def __init__(self, *, min_relevance: float = 0.03, budget_chars: int = 1500,
                 max_items: int = 6, min_len: int = 25, strong: float = 0.30,
                 rel_ratio: float = 0.45):
        self.min_relevance = min_relevance      # absolute floor: drop weak matches
        self.rel_ratio = rel_ratio              # relative floor: drop items far below the top
        self.budget_chars = budget_chars        # cap: don't over-inject
        self.max_items = max_items
        self.min_len = min_len                  # drop trivially short low-signal items
        self.strong = strong                    # relevance above which short items are kept

    def _probes(self, goal: str) -> list[str]:
        """The goal plus its salient sub-phrases — so discovery isn't single-shot."""
        probes = [goal]
        for clause in _SPLIT.split(goal):
            c = clause.strip()
            if len(c) >= 8 and c.lower() != goal.lower():
                probes.append(c)
        return probes[:5]

    def assemble(self, goal: str, memory) -> ContextBundle:
        # Discover: probe the goal + sub-phrases, keep each memory's BEST match.
        best: dict[str, tuple] = {}   # lesson id -> (lesson, relevance, score)
        for probe in self._probes(goal):
            for lesson, rel, score in memory.recall_scored(probe, k=self.max_items * 2,
                                                           touch=False):
                cur = best.get(lesson.id)
                if cur is None or score > cur[2]:
                    best[lesson.id] = (lesson, rel, score)

        ranked = sorted(best.values(), key=lambda x: x[2], reverse=True)
        # Relative floor: on top of the absolute floor, drop anything far below the
        # best match — scale-invariant, so it discriminates even with weak vectors.
        top_rel = max((rel for _, rel, _ in ranked), default=0.0)
        floor = max(self.min_relevance, self.rel_ratio * top_rel)

        # Curate: relevance floor, drop trivial low-signal, de-dup, budget cap.
        selected, seen, chars = [], set(), 0
        for lesson, rel, _score in ranked:
            if rel < floor:
                continue
            text = lesson.text.strip()
            if len(text) < self.min_len and rel < self.strong:
                continue                                   # trivial + weak → noise
            key = re.sub(r"\s+", " ", text[:80]).lower()
            if key in seen:
                continue                                   # near-duplicate
            if selected and chars + len(text) > self.budget_chars:
                break                                      # keep it lean
            selected.append((lesson, rel))
            seen.add(key)
            chars += len(text)
            if len(selected) >= self.max_items:
                break

        return ContextBundle(
            lessons=[le.text for le, _ in selected],
            items=selected,
            considered=len(best),
            dropped=len(best) - len(selected),
            chars=chars,
        )
