"""Tamper-evident audit ledger (Constitution C4 + gate G_AUDIT).

Every consequential action appends a JSON line carrying actor, action,
rationale, the constitutional decision, and a hash that chains to the previous
entry. Breaking or editing history breaks the chain, so tampering is detectable
(``verify``). The ledger is the factory's memory and its accountability.
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

GENESIS = "0" * 64

# One lock per ledger *file* (not per instance), so that multiple AuditLedger
# instances pointing at the same path — the capability runner, the factory
# orchestrator, the evolution engine, tool wrappers, all firing from fan-out
# threads — serialize their appends and never interleave the hash chain.
_PATH_LOCKS: dict[str, threading.Lock] = {}
_PATH_LOCKS_GUARD = threading.Lock()


def _lock_for(path: Path) -> threading.Lock:
    key = str(path.resolve())
    with _PATH_LOCKS_GUARD:
        lock = _PATH_LOCKS.get(key)
        if lock is None:
            lock = threading.Lock()
            _PATH_LOCKS[key] = lock
        return lock


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
        # Shared per-file lock so concurrent instances/threads can't interleave.
        self._lock = _lock_for(self.path)

    def _file_tail(self) -> tuple[str, int]:
        """Authoritative (prev_hash, next_seq) read from the file itself.

        Reading the true tail on every append — rather than trusting per-instance
        in-memory state — is what keeps the chain intact when more than one
        AuditLedger writes to the same file. Only the last record is needed, so a
        bounded tail read is used, with a full-read fallback for oversized records.
        """
        try:
            size = self.path.stat().st_size
        except FileNotFoundError:
            return GENESIS, 0
        if size == 0:
            return GENESIS, 0
        window = min(size, 65536)
        with self.path.open("rb") as fh:
            fh.seek(size - window)
            chunk = fh.read()
        lines = [ln for ln in chunk.splitlines() if ln.strip()]
        # If the window began mid-record (only a partial first line survived) or
        # the last line won't parse, fall back to reading the whole file.
        last_obj = None
        if lines:
            try:
                last_obj = json.loads(lines[-1].decode("utf-8"))
            except ValueError:
                last_obj = None
        if last_obj is None or window < size and len(lines) < 2:
            all_lines = [ln for ln in self.path.read_bytes().splitlines() if ln.strip()]
            if not all_lines:
                return GENESIS, 0
            last_obj = json.loads(all_lines[-1].decode("utf-8"))
        return last_obj["hash"], int(last_obj["seq"]) + 1

    def next_seq(self) -> int:
        """Seq the next appended entry will carry (== entry count for an intact chain)."""
        return self._file_tail()[1]

    def append(
        self,
        actor: str,
        action: str,
        rationale: str = "",
        decision: str = "INFO",
        data: dict | None = None,
    ) -> LedgerEntry:
        with self._lock:
            prev_hash, seq = self._file_tail()
            entry = LedgerEntry(
                seq=seq,
                ts=time.time(),
                actor=actor,
                action=action,
                rationale=rationale,
                decision=decision,
                prev_hash=prev_hash,
                data=data or {},
            )
            entry.hash = entry.compute_hash()
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(asdict(entry), separators=(",", ":")) + "\n")
                fh.flush()
                os.fsync(fh.fileno())
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
