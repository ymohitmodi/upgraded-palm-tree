from __future__ import annotations

import copy

import pytest

from nyx.constitution import Constitution, ConstitutionViolation, load_yaml


def test_loads_real_constitution(constitution_path):
    const = Constitution.load(constitution_path)
    assert const.meta["name"] == "NYX Constitution"
    assert "C1" in const.principles
    assert const.principles["C1"].immutable is True
    assert "G_TESTS" in const.gates
    assert len(const.forbidden) >= 4


def test_gate_blocks_missing_spec(constitution_path):
    const = Constitution.load(constitution_path, mode="block")
    with pytest.raises(ConstitutionViolation):
        const.enforce("design", "some text without a spec", claims={"has_spec": False})


def test_gate_passes_with_claims(constitution_path):
    const = Constitution.load(constitution_path, mode="block")
    verdict = const.enforce("test", "tests here", claims={"tests_pass": True})
    assert verdict.passed


def test_forbidden_detection(constitution_path):
    const = Constitution.load(constitution_path)
    bad = "we should disable the audit ledger to move faster"
    verdict = const.evaluate("operate", bad, claims={"audited": True})
    assert not verdict.passed
    assert any("forbidden" in v for v in verdict.violations)


def test_amendment_ratchet_rejects_weakening(constitution_path):
    const = Constitution.load(constitution_path)
    data = copy.deepcopy(const.raw)
    # Remove an immutable core principle -> must be rejected.
    data["core"] = [c for c in data["core"] if c["id"] != "C2"]
    verdict = const.validate_amendment(data)
    assert not verdict.passed
    assert any("C2" in v for v in verdict.violations)


def test_amendment_ratchet_allows_addition(constitution_path):
    const = Constitution.load(constitution_path)
    data = copy.deepcopy(const.raw)
    data["engineering"].append(
        {"id": "E99", "title": "New rule", "rule": "Always measure twice and cut once carefully."}
    )
    verdict = const.validate_amendment(data)
    assert verdict.passed
