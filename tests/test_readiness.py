"""Go-live preflight readiness checks (offline / config-only)."""
from __future__ import annotations

from nyx.readiness import FAIL, PASS, WARN, preflight, verdict


def _cfg(tmp_path, **over):
    from nyx.config import load_config

    cfg = load_config(dotenv=False)
    cfg.ledger_path = str(tmp_path / "l.jsonl")
    for k, v in over.items():
        setattr(cfg, k, v)
    return cfg


def test_general_preflight_reports_mock_brain(tmp_path):
    checks = preflight(_cfg(tmp_path), probe=False)   # no key → mock
    names = {c.name: c for c in checks}
    assert names["brain"].status == WARN and "MOCK" in names["brain"].detail
    assert names["governance"].status == PASS         # default constitution_mode=block
    assert "state-dir" in names


def test_investing_preflight_flags_missing_edgar(tmp_path):
    cfg = _cfg(tmp_path)          # no EDGAR_IDENTITY, edgartools not installed in CI
    checks = preflight(cfg, capability="value-investing", probe=False)
    names = {c.name: c for c in checks}
    assert names["edgar-identity"].status == FAIL and names["edgar-identity"].fix
    assert "edgartools" in names
    assert verdict(checks) == FAIL                     # missing hard deps → FAIL


def test_investing_preflight_passes_identity_when_set(tmp_path):
    cfg = _cfg(tmp_path, edgar_identity="Jane Doe jane@example.com")
    names = {c.name: c for c in preflight(cfg, capability="value-investing")}
    assert names["edgar-identity"].status == PASS


def test_verdict_precedence():
    from nyx.readiness import Check

    assert verdict([Check("a", PASS), Check("b", WARN)]) == WARN
    assert verdict([Check("a", PASS), Check("b", FAIL), Check("c", WARN)]) == FAIL
    assert verdict([Check("a", PASS)]) == PASS


def test_governance_warns_when_not_fail_closed(tmp_path):
    cfg = _cfg(tmp_path, constitution_mode="warn")
    names = {c.name: c for c in preflight(cfg)}
    assert names["governance"].status == WARN and names["governance"].fix
