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
from ..security.guardrails import detect_injection, scan_secrets
from ..security.sandbox import run_sandboxed

_TESTish = re.compile(r"^\s*(def\s+test|assert\b|import\b|from\b|@)")

# Dangerous code constructs a security review must never wave through.
_DANGER = [
    ("eval", re.compile(r"\beval\s*\(")),
    ("exec", re.compile(r"\bexec\s*\(")),
    ("os.system", re.compile(r"\bos\.system\s*\(")),
    ("shell=True", re.compile(r"subprocess\.\w+\([^)]*shell\s*=\s*True")),
    ("pickle.loads", re.compile(r"\bpickle\.loads\s*\(")),
    ("unsafe_yaml", re.compile(r"\byaml\.load\s*\((?![^)]*Loader)")),
    ("os_popen", re.compile(r"\bos\.popen\s*\(")),
]


@dataclass
class VerifyResult:
    ran: bool          # was there runnable code + tests to execute?
    passed: bool       # did execution succeed?
    detail: str = ""


@dataclass
class SecurityVerdict:
    ok: bool
    findings: list[str]


_ACCEPT_RE = re.compile(r"acceptance criteria|\bAC\d|\bgiven\b.*\bthen\b", re.IGNORECASE)
_NONGOAL_RE = re.compile(r"non[- ]?goal|out of scope|not (building|in scope|doing)", re.IGNORECASE)
_REVERSIBLE_RE = re.compile(
    r"roll ?back|revert|reversible|blue[- ]?green|canary|feature[- ]?flag|previous revision",
    re.IGNORECASE)


def verify_spec(artifact: str) -> SecurityVerdict:
    """G_SPEC source: the design must actually contain acceptance criteria AND
    non-goals — not just an agent asserting HAS_SPEC=true."""
    findings = []
    if not _ACCEPT_RE.search(artifact):
        findings.append("spec:no acceptance criteria")
    if not _NONGOAL_RE.search(artifact):
        findings.append("spec:no non-goals/out-of-scope")
    return SecurityVerdict(ok=not findings, findings=findings)


def verify_deploy(artifact: str) -> SecurityVerdict:
    """G_DEPLOY source: the release plan must describe a real reversibility /
    rollback mechanism, not just assert DEPLOY_REVERSIBLE=true."""
    ok = bool(_REVERSIBLE_RE.search(artifact))
    return SecurityVerdict(ok=ok, findings=[] if ok else ["deploy:no rollback/reversibility described"])


def verify_audit(ledger, entries_this_run: int, *, min_entries: int = 3) -> SecurityVerdict:
    """G_AUDIT source: derive `audited` from the ledger itself — the hash chain
    must verify (tamper-evident) and this run must have actually written entries
    — instead of trusting the operator agent's AUDITED=true."""
    findings = []
    try:
        if not ledger.verify():
            findings.append("audit:ledger hash chain broken")
    except Exception as exc:  # noqa: BLE001
        findings.append(f"audit:verify failed ({exc})")
    if entries_this_run < min_entries:
        findings.append(f"audit:only {entries_this_run} ledger entries this run")
    return SecurityVerdict(ok=not findings, findings=findings)


def verify_security(artifact: str) -> SecurityVerdict:
    """Scan the produced code for real security problems — the authoritative
    source of ``security_ok``, so the G_SECURITY gate cannot be satisfied by an
    agent merely asserting ``SECURITY_OK=true``.

    Fail-closed: any secret, injection signal, or dangerous construct vetoes the
    gate regardless of what the security agent claimed about itself."""
    code = extract_code(artifact) or artifact
    findings: list[str] = []
    findings += [f"secret:{s}" for s in scan_secrets(code)]
    findings += [f"injection:{i[:40]}" for i in detect_injection(code)]
    findings += [f"danger:{name}" for name, pat in _DANGER if pat.search(code)]
    return SecurityVerdict(ok=not findings, findings=findings)


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
