"""Standing evaluation harness — turn "it got better" into a persisted chart.

Runs each capability's **held-out** suite (contamination-controlled: the eval
tasks/universes are disjoint from what evolution trains on), records a timestamped
score, and keeps the history so you can see the trend over time and the delta
since the last run — the trust artifact that makes compounding *visible*, not
merely claimed.

    harness = EvalHarness(config)
    for rec in harness.run_all():
        print(rec.capability, rec.score, harness.delta(rec.capability))
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class EvalRecord:
    ts: float
    capability: str
    score: float
    detail: str = ""


def _sparkline(values: list[float]) -> str:
    if not values:
        return ""
    blocks = "▁▂▃▄▅▆▇█"
    lo, hi = min(values), max(values)
    span = (hi - lo) or 1.0
    return "".join(blocks[min(len(blocks) - 1, int((v - lo) / span * (len(blocks) - 1)))]
                   for v in values)


class EvalHarness:
    def __init__(self, config, provider=None):
        self.config = config
        if provider is None:
            from .providers import build_provider
            provider = build_provider(config)
        self.provider = provider
        self.path = Path(config.eval_history)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    # -- persistence ---------------------------------------------------------
    def _all(self) -> list[EvalRecord]:
        if not self.path.exists():
            return []
        return [EvalRecord(**json.loads(ln)) for ln in
                self.path.read_text(encoding="utf-8").splitlines() if ln.strip()]

    def history(self, capability: str) -> list[EvalRecord]:
        return [r for r in self._all() if r.capability == capability]

    def _append(self, rec: EvalRecord) -> None:
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(asdict(rec), separators=(",", ":")) + "\n")

    # -- running -------------------------------------------------------------
    def run(self, capability) -> EvalRecord | None:
        result = capability.eval(self.config, self.provider)
        if result is None:
            return None
        rec = EvalRecord(ts=time.time(), capability=capability.name,
                         score=round(result.score, 4), detail=result.detail)
        self._append(rec)
        return rec

    def run_all(self) -> list[EvalRecord]:
        from .capabilities import all_capabilities

        out = []
        for cap in all_capabilities():
            rec = self.run(cap)
            if rec is not None:
                out.append(rec)
        return out

    # -- reporting -----------------------------------------------------------
    def delta(self, capability: str) -> float | None:
        """Score change from the previous recorded eval (None if first ever)."""
        hist = self.history(capability)
        if len(hist) < 2:
            return None
        return round(hist[-1].score - hist[-2].score, 4)

    def trend(self, capability: str) -> str:
        return _sparkline([r.score for r in self.history(capability)])
