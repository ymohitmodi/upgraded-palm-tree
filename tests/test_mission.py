from __future__ import annotations

from nyx.constitution import Constitution
from nyx.evolution.archive import Archive
from nyx.evolution.engine import EvolutionEngine
from nyx.mission import MissionControl
from nyx.providers.mock import MockProvider


def _control(config, constitution_path, **kw):
    const = Constitution.load(constitution_path, mode=config.constitution_mode)
    return MissionControl(
        config=config,
        provider=MockProvider(config),
        constitution=const,
        **kw,
    )


def test_plan_decomposes_objective(config, constitution_path):
    mc = _control(config, constitution_path)
    backlog = mc.plan("Launch a SaaS analytics product")
    assert 1 <= len(backlog) <= 6
    assert all(isinstance(x, str) and x for x in backlog)


def test_mission_ships_backlog_autonomously(config, constitution_path):
    config.autonomy = "autonomous"
    mc = _control(config, constitution_path)
    report = mc.run("Build a billing system", max_cycles=4, evolve_every=2, generations=3)
    assert report.cycles, report.summary()
    assert report.shipped == len(report.cycles)  # all shipped in autonomous mode
    assert report.productivity == 1.0
    assert report.ledger_ok


def test_evolution_runs_and_genome_is_adopted(config, constitution_path):
    config.autonomy = "autonomous"
    mc = _control(config, constitution_path)
    mc.run("Ship a feature set", max_cycles=4, evolve_every=2, generations=4)
    # Evolution populated the shared archive and a coder genome was adopted.
    assert len(mc.archive) >= 1
    assert mc.archive.best_for("coder") is not None
    assert "coder" in mc.genomes


def test_genome_carries_over_between_missions(config, constitution_path):
    config.autonomy = "autonomous"
    archive = Archive(config.evolution_archive)
    mc1 = _control(config, constitution_path, archive=archive)
    mc1.run("First objective", max_cycles=2, evolve_every=1, generations=4)

    # A fresh controller on the same archive should adopt the evolved genome.
    mc2 = _control(config, constitution_path, archive=Archive(config.evolution_archive))
    report = mc2.run("Second objective", max_cycles=2, evolve_every=0, generations=0)
    assert report.genome_score_before is not None  # carried over from mc1
    assert "coder" in mc2.genomes


def test_keep_going_replans_when_backlog_empties(config, constitution_path):
    config.autonomy = "autonomous"
    mc = _control(config, constitution_path)
    report = mc.run("Keep improving", max_cycles=8, evolve_every=0, keep_going=True)
    # With keep_going it should run up to the cycle cap, not stop at first backlog.
    assert len(report.cycles) > 3


def test_shared_empty_archive_is_not_discarded(config, constitution_path):
    """Regression: Archive defines __len__, so `archive or Archive()` would
    silently replace an empty shared archive. Ensure identity is preserved."""
    const = Constitution.load(constitution_path)
    archive = Archive(config.evolution_archive)
    engine = EvolutionEngine(
        config=config,
        provider=MockProvider(config),
        constitution=const,
        archive=archive,
    )
    assert engine.archive is archive
    engine.evolve(generations=2)
    assert len(archive) >= 1  # writes landed in the shared object
