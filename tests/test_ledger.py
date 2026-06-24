from __future__ import annotations

import json

from nyx.observability.ledger import AuditLedger


def test_append_and_verify(tmp_path):
    path = tmp_path / "l.jsonl"
    ledger = AuditLedger(path)
    ledger.append("factory", "run_start", rationale="x", decision="INFO")
    ledger.append("agent:coder", "produce_artifact", decision="INFO")
    assert ledger.verify() is True
    assert len(ledger.read()) == 2


def test_tamper_is_detected(tmp_path):
    path = tmp_path / "l.jsonl"
    ledger = AuditLedger(path)
    ledger.append("a", "one")
    ledger.append("b", "two")

    # Tamper with the first entry's content.
    lines = path.read_text().splitlines()
    first = json.loads(lines[0])
    first["rationale"] = "tampered"
    lines[0] = json.dumps(first)
    path.write_text("\n".join(lines) + "\n")

    fresh = AuditLedger(path)
    assert fresh.verify() is False


def test_chain_continues_across_instances(tmp_path):
    path = tmp_path / "l.jsonl"
    AuditLedger(path).append("a", "one")
    second = AuditLedger(path)
    second.append("b", "two")
    assert second.verify() is True
    assert len(second.read()) == 2
