"""Gates must verify, not trust: executed tests override self-graded claims."""
from __future__ import annotations

from nyx.constitution import Constitution
from nyx.factory.orchestrator import Factory
from nyx.factory.verify import verify_artifact, verify_security
from nyx.providers.base import Completion


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
            sysmsg = next((m.content for m in messages if m.role == "system"), "")
            role = sysmsg.split("ROLE=", 1)[-1].split("\n", 1)[0].strip()
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
            sysmsg = next((m.content for m in messages if m.role == "system"), "")
            role = sysmsg.split("ROLE=", 1)[-1].split("\n", 1)[0].strip()
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
