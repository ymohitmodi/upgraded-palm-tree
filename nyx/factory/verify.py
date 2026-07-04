"""Verify artifacts instead of trusting agents' self-graded claims.

A gate that reads ``TESTS_PASS=true`` from the agent that wrote the code is the
agent grading its own homework — the classic failure of "autonomous" pipelines.
This module executes the produced code against the produced tests **in the
secure sandbox** and returns the real result, so the G_TESTS gate reflects
reality, not a self-report. When there is nothing runnable to check (freeform
artifacts), it says so (``ran=False``) and the caller keeps the claim but records
that it was *unverified* — honest either way.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from ..evolution.benchmarks import extract_code
from ..security.sandbox import run_sandboxed

_TESTish = re.compile(r"^\s*(def\s+test|assert\b|import\b|from\b|@)")


@dataclass
class VerifyResult:
    ran: bool          # was there runnable code + tests to execute?
    passed: bool       # did execution succeed?
    detail: str = ""


def _extract_tests(text: str) -> str:
    """Pull the test lines (def test_*, asserts, imports, their bodies) out of a
    tester artifact, dropping prose and self-graded markers like TESTS_PASS=true."""
    block = extract_code(text)
    kept: list[str] = []
    for line in block.splitlines():
        if _TESTish.match(line) or line.startswith((" ", "\t")) or not line.strip():
            kept.append(line)
    return "\n".join(kept).strip()


def verify_artifact(build_artifact: str, test_artifact: str, *, timeout: float = 10.0) -> VerifyResult:
    """Run the build's code against the tester's tests in the sandbox."""
    code = extract_code(build_artifact)
    tests = _extract_tests(test_artifact)
    has_tests = ("assert" in tests) or ("def test" in tests)
    if not code or not has_tests:
        return VerifyResult(ran=False, passed=False, detail="no runnable code+tests")

    harness = (
        code + "\n\n# ---- executed tests ----\n" + tests + "\n\n"
        "_tests = [v for k, v in dict(globals()).items() "
        "if k.startswith('test_') and callable(v)]\n"
        "for _t in _tests:\n    _t()\n"
        "print('VERIFIED_OK')\n"
    )
    sb = run_sandboxed(harness, timeout=timeout)
    passed = sb.ok and "VERIFIED_OK" in sb.stdout
    detail = "ok" if passed else (sb.stderr.strip().splitlines()[-1:] or ["failed"])[0]
    return VerifyResult(ran=True, passed=passed, detail=detail)
