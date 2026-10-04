"""The single autonomous loop: CapabilityRunner driving the software factory.

(These migrated from the retired MissionControl tests — same guarantees, one loop.)
"""
from __future__ import annotations

from nyx.capabilities import CapabilityRunner
from nyx.capabilities.software import SoftwareFactoryCapability
from nyx.constitution import Constitution
from nyx.evolution.archive import Archive
from nyx.evolution.engine import EvolutionEngine
from nyx.providers.mock import MockProvider


def _runner(config, **kw):
    return CapabilityRunner(SoftwareFactoryCapability(), config=config,
                            provider=MockProvider(config), **kw)


def test_plan_decomposes_objective(config, constitution_path):
    runner = _runner(config)
    backlog = SoftwareFactoryCapability().plan("Launch a SaaS analytics product", runner._ctx())
    assert backlog and all(isinstance(x, str) and x for x in backlog)


def test_runs_backlog_autonomously(config, constitution_path):
    config.autonomy = "autonomous"
    report = _runner(config).run("Build a billing system", max_cycles=4,
                                 evolve_every=2, generations=3, refresh_every=0)
    assert report.cycles, report.summary()
    assert all(c.ok for c in report.cycles)      # all shipped in autonomous mode
    assert report.ledger_ok


def test_evolution_runs_and_genome_is_adopted(config, constitution_path):
    config.autonomy = "autonomous"
    runner = _runner(config)
    runner.run("Ship a feature set", max_cycles=4, evolve_every=2, generations=4, refresh_every=0)
    assert len(runner.archive) >= 1
    assert runner.archive.best_for("coder") is not None
    assert "coder" in runner.genomes


def test_genome_carries_over_between_runs(config, constitution_path):
    config.autonomy = "autonomous"
    archive = Archive(config.evolution_archive)
    r1 = CapabilityRunner(SoftwareFactoryCapability(), config=config,
                          provider=MockProvider(config), archive=archive)
    r1.run("First objective", max_cycles=2, evolve_every=1, generations=4, refresh_every=0)

    r2 = CapabilityRunner(SoftwareFactoryCapability(), config=config,
                          provider=MockProvider(config),
                          archive=Archive(config.evolution_archive))
    report = r2.run("Second objective", max_cycles=2, evolve_every=0,
                    generations=0, refresh_every=0)
    assert report.genome_score_before is not None   # carried over from r1
    assert "coder" in r2.genomes


def test_respects_shared_call_budget(config, constitution_path):
    """Codex P1: one budget across planning + every cycle + evolution."""
    config.autonomy = "autonomous"
    config.fanout = 2
    config.max_calls = 20
    report = _runner(config).run("A large objective with many features",
                                 max_cycles=10, evolve_every=0, refresh_every=0)
    assert report.calls <= config.max_calls + 6
    assert report.budget_exhausted


def test_keep_going_replans_when_backlog_empties(config, constitution_path):
    config.autonomy = "autonomous"
    report = _runner(config).run("Keep improving", max_cycles=8, evolve_every=0,
                                 refresh_every=0, keep_going=True)
    assert len(report.cycles) > 3


def test_evolution_is_role_scoped_on_shared_archive(config, constitution_path):
    """Codex P2: evolving a new role on a populated archive still seeds it."""
    const = Constitution.load(constitution_path)
    archive = Archive(config.evolution_archive)
    provider = MockProvider(config)

    EvolutionEngine(config=config, provider=provider, constitution=const,
                    archive=archive, role="coder").evolve(generations=4)
    assert archive.best_for("reviewer") is None

    report = EvolutionEngine(config=config, provider=provider, constitution=const,
                             archive=archive, role="reviewer").evolve(generations=4)
    assert archive.best_for("reviewer") is not None
    assert report.best_genome.get("role") == "reviewer"


def test_shared_empty_archive_is_not_discarded(config, constitution_path):
    """Regression: an empty shared Archive (falsy via __len__) must be preserved."""
    const = Constitution.load(constitution_path)
    archive = Archive(config.evolution_archive)
    engine = EvolutionEngine(config=config, provider=MockProvider(config),
                             constitution=const, archive=archive)
    assert engine.archive is archive
    engine.evolve(generations=2)
    assert len(archive) >= 1
