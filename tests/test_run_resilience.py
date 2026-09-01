"""A multi-hour `nyx run` must survive a single flaky cycle, tool, or network
call — the exact failure mode that killed an 8-hour mission on an embedding
timeout. One bad step should cost that step, never the whole mission."""
from __future__ import annotations

import pytest

from nyx.capabilities import CapabilityRunner
from nyx.capabilities.base import Capability, CycleContext, CycleResult
from nyx.providers.mock import MockProvider


class _FlakyCapability(Capability):
    """A minimal capability whose hooks fail on command, to exercise the
    runner's guards without touching real network/tool code."""
    name = "flaky"
    description = "test double"

    def __init__(self, fail_execute_on=(), fail_refresh_on=(), fail_evolve=False,
                fail_consolidate=False):
        self.fail_execute_on = set(fail_execute_on)
        self.fail_refresh_on = set(fail_refresh_on)
        self.fail_evolve = fail_evolve
        self.fail_consolidate = fail_consolidate
        self.executed: list[str] = []
        self.refreshed: list[int] = []

    def matches(self, objective: str) -> bool:
        return True

    def plan(self, objective, ctx):
        return ["cycle-1", "cycle-2", "cycle-3", "cycle-4"]

    def refresh_knowledge(self, ctx: CycleContext) -> dict:
        self.refreshed.append(ctx.cycle_index)
        if ctx.cycle_index in self.fail_refresh_on:
            raise ConnectionError("simulated network timeout")
        return {"ok": True}

    def execute(self, task: str, ctx: CycleContext) -> CycleResult:
        self.executed.append(task)
        if task in self.fail_execute_on:
            raise TimeoutError("simulated hung embedding call")
        if self.fail_consolidate:
            # consolidate() failure is exercised via monkeypatch in its own test;
            # this branch is unused here.
            pass
        return CycleResult(item=task, ok=True, score=0.5)

    def benchmark(self, ctx: CycleContext):
        if self.fail_evolve:
            def boom(agent):
                raise RuntimeError("simulated benchmark network failure")
            return boom
        return None


def test_one_failed_cycle_does_not_end_the_mission(config, constitution_path):
    cap = _FlakyCapability(fail_execute_on={"cycle-2"})
    runner = CapabilityRunner(cap, config=config, provider=MockProvider(config))
    report = runner.run("test objective", max_cycles=4, evolve_every=0, refresh_every=0)

    assert len(report.cycles) == 4                     # all 4 cycles ran to completion
    outcomes = {c.item: c.ok for c in report.cycles}
    assert outcomes == {"cycle-1": True, "cycle-2": False,
                        "cycle-3": True, "cycle-4": True}
    failed = next(c for c in report.cycles if c.item == "cycle-2")
    assert failed.blocked_at == "ERROR" and "TimeoutError" in failed.summary
    assert report.ledger_ok                             # the ledger stayed intact
    entries = runner.ledger.read()
    assert any(e.action == "cycle_error" for e in entries)
    assert any(e.action == "run_end" for e in entries)  # the mission finished normally


def test_refresh_knowledge_failure_does_not_skip_the_cycle(config, constitution_path):
    """A knowledge-refresh network failure must not prevent that cycle's decision
    from still being made — only the refresh step is lost."""
    cap = _FlakyCapability(fail_refresh_on={1})
    runner = CapabilityRunner(cap, config=config, provider=MockProvider(config))
    report = runner.run("test objective", max_cycles=2, evolve_every=0, refresh_every=1)

    assert len(report.cycles) == 2
    assert all(c.ok for c in report.cycles)             # execute still ran both times
    assert cap.executed == ["cycle-1", "cycle-2"]
    entries = runner.ledger.read()
    assert any(e.action == "refresh_knowledge_error" for e in entries)
    assert any(e.action == "run_end" for e in entries)


def test_evolution_failure_does_not_end_the_mission(config, constitution_path):
    cap = _FlakyCapability(fail_evolve=True)
    runner = CapabilityRunner(cap, config=config, provider=MockProvider(config))
    report = runner.run("test objective", max_cycles=2, evolve_every=1, generations=2,
                        refresh_every=0)

    assert len(report.cycles) == 2 and all(c.ok for c in report.cycles)
    assert report.evolutions == 0                        # the failed evolution wasn't counted
    entries = runner.ledger.read()
    assert any(e.action == "evolution_error" for e in entries)
    assert any(e.action == "run_end" for e in entries)


def test_consolidate_failure_does_not_end_the_mission(config, constitution_path, monkeypatch):
    cap = _FlakyCapability()
    runner = CapabilityRunner(cap, config=config, provider=MockProvider(config))

    def boom(*a, **kw):
        raise OSError("simulated disk error mid-write")
    monkeypatch.setattr(runner.memory, "consolidate", boom)

    report = runner.run("test objective", max_cycles=2, evolve_every=0,
                        consolidate_every=1, refresh_every=0)
    assert len(report.cycles) == 2 and all(c.ok for c in report.cycles)
    entries = runner.ledger.read()
    assert any(e.action == "consolidate_error" for e in entries)
    assert any(e.action == "run_end" for e in entries)


def test_keyboard_interrupt_still_propagates(config, constitution_path):
    """The resilience guard must catch ordinary failures but NEVER swallow a
    deliberate user interrupt — that must still stop the run immediately."""
    class _InterruptingCapability(_FlakyCapability):
        def execute(self, task, ctx):
            if task == "cycle-2":
                raise KeyboardInterrupt
            return super().execute(task, ctx)

    runner = CapabilityRunner(_InterruptingCapability(), config=config,
                              provider=MockProvider(config))
    with pytest.raises(KeyboardInterrupt):
        runner.run("test objective", max_cycles=4, evolve_every=0, refresh_every=0)
