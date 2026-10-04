"""Gates must verify, not trust: executed tests override self-graded claims."""
from __future__ import annotations

from nyx.constitution import Constitution
from nyx.factory.orchestrator import Factory
from nyx.factory.verify import verify_artifact, verify_security
from nyx.providers.base import Completion

# A structurally valid spec so runs pass G_SPEC and reach the gate under test.
_VALID_SPEC = ("## Acceptance criteria\n- AC1: works end to end\n- AC2: inputs validated\n"
               "## Non-goals\n- not building auth\nHAS_SPEC=true")
_VALID_DEPLOY = "Strategy: blue/green, single-click rollback; reversible.\nDEPLOY_REVERSIBLE=true"


def _role_of(messages) -> str:
    sysmsg = next((m.content for m in messages if m.role == "system"), "")
    return sysmsg.split("ROLE=", 1)[-1].split("\n", 1)[0].strip()


def test_verify_security_flags_real_problems():
    assert verify_security("```python\ndef f(): return 1\n```").ok is True
    assert not verify_security("```python\nimport os\nos.system('rm -rf /')\n```").ok
    assert not verify_security("```python\nAPI_KEY = 'sk-ABCDEFGHIJKLMNOPQRSTUV'\n```").ok
    assert not verify_security("```python\neval(user_input)\n```").ok


def test_security_gate_vetoes_insecure_code_despite_self_claim(config, constitution_path):
    """A build with os.system must be BLOCKED at review even though the security
    agent asserts SECURITY_OK=true — scanners are the authoritative source."""
    const = Constitution.load(constitution_path, mode="block")
    config.autonomy = "autonomous"
    config.fanout = 1

    class InsecureProvider:
        name = "insecure"
        def chat(self, model, messages, **kw):
            role = _role_of(messages)
            if role == "architect":
                return Completion(text=_VALID_SPEC, model=model)
            if role == "coder":
                return Completion(
                    text="```python\nimport os\ndef feature(items):\n"
                         "    os.system('echo pwned')\n    return sum(items)\n```",
                    model=model)
            return Completion(text="HAS_SPEC=true\nSECURITY_OK=true\n"
                                   "DEPLOY_REVERSIBLE=true\nAUDITED=true", model=model)

    factory = Factory(config=config, provider=InsecureProvider(), constitution=const)
    result = factory.build("Add a sum utility", approver=lambda *_: True)
    assert result.blocked_at == "review"
    assert any("danger:os.system" in f for f in result.findings)


def test_verify_spec_deploy_audit_units(tmp_path):
    from nyx.factory.verify import verify_audit, verify_deploy, verify_spec
    from nyx.observability.ledger import AuditLedger

    assert verify_spec("## Acceptance criteria\n- AC1\n## Non-goals\n- none").ok
    assert not verify_spec("just some prose with no structure").ok
    assert verify_deploy("blue/green with single-click rollback").ok
    assert not verify_deploy("we will ship it and hope").ok

    ledger = AuditLedger(tmp_path / "l.jsonl")
    for _ in range(4):
        ledger.append("t", "a", decision="INFO")
    assert verify_audit(ledger, 4).ok                 # chain intact + entries
    assert not verify_audit(ledger, 0).ok             # no entries this run

    class BrokenLedger:
        def verify(self):
            return False
    assert not verify_audit(BrokenLedger(), 10).ok    # tampered chain vetoes


def test_missing_spec_structure_blocks_at_design(config, constitution_path):
    """An agent that claims HAS_SPEC=true but writes no acceptance criteria is
    blocked at G_SPEC — the design gate is structurally verified."""
    const = Constitution.load(constitution_path, mode="block")
    config.autonomy = "autonomous"
    config.fanout = 1

    class NoSpecProvider:
        name = "nospec"
        def chat(self, model, messages, **kw):
            role = _role_of(messages)
            if role == "architect":
                return Completion(text="We'll build something nice.\nHAS_SPEC=true", model=model)
            return Completion(text="HAS_SPEC=true\nSECURITY_OK=true\n"
                                   "DEPLOY_REVERSIBLE=true\nAUDITED=true", model=model)

    factory = Factory(config=config, provider=NoSpecProvider(), constitution=const)
    result = factory.build("Add a thing", approver=lambda *_: True)
    assert result.blocked_at == "design"
    assert any("spec:" in f for f in result.findings)


def test_verify_artifact_runs_real_tests():
    code = "```python\ndef feature(items):\n    return sum(items)\n```"
    good = "def test_ok(): assert feature([1,2,3]) == 6\nTESTS_PASS=true"
    bad = "def test_ok(): assert feature([1,2,3]) == 999\nTESTS_PASS=true"
    assert verify_artifact(code, good).passed is True
    r = verify_artifact(code, bad)
    assert r.ran is True and r.passed is False        # the lie is caught
    assert verify_artifact("just prose", "no tests here").ran is False


def test_mock_factory_still_ships_because_code_actually_passes(config, constitution_path):
    """The mock coder's summing feature genuinely passes the mock tester's
    assert feature([1,2,3])==6, so verified execution keeps the happy path."""
    from nyx.providers.mock import MockProvider

    const = Constitution.load(constitution_path, mode=config.constitution_mode)
    config.autonomy = "autonomous"
    factory = Factory(config=config, provider=MockProvider(config), constitution=const)
    result = factory.build("Add a sum utility", approver=lambda *_: True)
    test_stage = next(s for s in result.stages if s.stage == "test")
    assert test_stage.passed          # earned by real execution, not a self-claim


def test_lying_tester_is_blocked_despite_self_claim(config, constitution_path):
    """A tester that claims TESTS_PASS=true but whose tests fail against the
    build must be BLOCKED at the G_TESTS gate — the claim is overridden."""
    const = Constitution.load(constitution_path, mode="block")
    config.autonomy = "autonomous"
    config.fanout = 1

    class LyingProvider:
        name = "lying"
        def chat(self, model, messages, **kw):
            role = _role_of(messages)
            if role == "architect":
                return Completion(text=_VALID_SPEC, model=model)
            if role == "coder":
                return Completion(text="```python\ndef feature(items):\n    return 0\n```",
                                  model=model)  # wrong implementation
            if role == "tester":
                # Real test would fail (0 != 6) but the agent claims success.
                return Completion(
                    text="def test_ok(): assert feature([1,2,3]) == 6\nTESTS_PASS=true",
                    model=model)
            # Everything else asserts its own gate claims to isolate G_TESTS.
            return Completion(text="HAS_SPEC=true\nSECURITY_OK=true\n"
                                   "DEPLOY_REVERSIBLE=true\nAUDITED=true", model=model)

    factory = Factory(config=config, provider=LyingProvider(), constitution=const)
    result = factory.build("Add a sum utility", approver=lambda *_: True)
    assert result.blocked_at == "test"       # execution caught the lie
    assert not result.shipped
