"""Tamper-evident audit ledger (Constitution C4 + gate G_AUDIT).

Every consequential action appends a JSON line carrying actor, action,
rationale, the constitutional decision, and a hash that chains to the previous
entry. Breaking or editing history breaks the chain, so tampering is detectable
(``verify``). The ledger is the factory's memory and its accountability.
"""
from __future__ import annotations

import hashlib
import json
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

GENESIS = "0" * 64


@dataclass
class LedgerEntry:
    seq: int
    ts: float
    actor: str
    action: str
    rationale: str
    decision: str  # PASS | BLOCK | INFO
    prev_hash: str
    data: dict = field(default_factory=dict)
    hash: str = ""

    def compute_hash(self) -> str:
        payload = {
            "seq": self.seq,
            "ts": round(self.ts, 6),
            "actor": self.actor,
            "action": self.action,
            "rationale": self.rationale,
            "decision": self.decision,
            "prev_hash": self.prev_hash,
            "data": self.data,
        }
        blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()


class AuditLedger:
    def __init__(self, path: str | Path = ".nyx/audit.ledger.jsonl"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()  # serialize appends across fan-out threads
        self._last_hash = self._load_last_hash()
        self._seq = self._load_seq()

    def _load_last_hash(self) -> str:
        if not self.path.exists():
            return GENESIS
        last = None
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                last = line
        if not last:
            return GENESIS
        return json.loads(last)["hash"]

    def _load_seq(self) -> int:
        if not self.path.exists():
            return 0
        return sum(1 for ln in self.path.read_text(encoding="utf-8").splitlines() if ln.strip())

    def append(
        self,
        actor: str,
        action: str,
        rationale: str = "",
        decision: str = "INFO",
        data: dict | None = None,
    ) -> LedgerEntry:
        with self._lock:
            entry = LedgerEntry(
                seq=self._seq,
                ts=time.time(),
                actor=actor,
                action=action,
                rationale=rationale,
                decision=decision,
                prev_hash=self._last_hash,
                data=data or {},
            )
            entry.hash = entry.compute_hash()
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(asdict(entry), separators=(",", ":")) + "\n")
            self._last_hash = entry.hash
            self._seq += 1
            return entry

    def read(self) -> list[LedgerEntry]:
        if not self.path.exists():
            return []
        out: list[LedgerEntry] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                out.append(LedgerEntry(**json.loads(line)))
        return out

    def verify(self) -> bool:
        """Return True iff the hash chain is intact (no tampering)."""
        prev = GENESIS
        for entry in self.read():
            if entry.prev_hash != prev:
                return False
            if entry.compute_hash() != entry.hash:
                return False
            prev = entry.hash
        return True

    def tail(self, n: int = 20) -> list[LedgerEntry]:
        return self.read()[-n:]
