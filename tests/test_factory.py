from __future__ import annotations

from nyx.constitution import Constitution
from nyx.factory.orchestrator import Factory
from nyx.providers.mock import MockProvider


def _factory(config, constitution_path):
    const = Constitution.load(constitution_path, mode=config.constitution_mode)
    return Factory(config=config, provider=MockProvider(config), constitution=const)


def test_full_pipeline_ships_when_autonomous(config, constitution_path):
    config.autonomy = "autonomous"
    factory = _factory(config, constitution_path)
    result = factory.build("Add a usage-based billing dashboard")
    assert result.shipped, result.summary()
    assert result.ledger_ok
    # All seven stages ran.
    stages = [s.stage for s in result.stages]
    assert stages == ["explore", "design", "build", "review", "test", "deploy", "operate"]


def test_fanout_generates_multiple_candidates(config, constitution_path):
    config.autonomy = "autonomous"
    config.fanout = 4
    factory = _factory(config, constitution_path)
    result = factory.build("Build a feature")
    design = next(s for s in result.stages if s.stage == "design")
    assert design.candidates == 4
    assert result.metrics["candidates_generated"] >= 4


def test_deploy_is_held_when_supervised(config, constitution_path):
    config.autonomy = "supervised"
    factory = _factory(config, constitution_path)
    # No approver -> deploy must be held, pipeline stops before operate.
    result = factory.build("Ship something")
    assert result.held_for_approval
    assert not result.shipped
    assert result.artifact("operate") is None


def test_supervised_ships_with_approval(config, constitution_path):
    config.autonomy = "supervised"
    factory = _factory(config, constitution_path)
    result = factory.build("Ship something", approver=lambda *_: True)
    assert not result.held_for_approval
    assert result.shipped


def test_budget_guard_stops_run(config, constitution_path):
    config.autonomy = "autonomous"
    config.max_calls = 1
    factory = _factory(config, constitution_path)
    result = factory.build("Anything")
    assert result.blocked_at is not None
    assert not result.shipped
