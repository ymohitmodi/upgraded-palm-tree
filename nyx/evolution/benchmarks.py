"""SWE-bench-style benchmark harness for the evolution engine.

A *real* fitness signal: give an agent a coding task, extract the code it
produces, run it against hidden unit tests **inside the secure sandbox**, and
score the fraction of tasks whose tests pass. This is the same shape as
SWE-bench (problem statement → candidate patch → run tests), scaled down to a
self-contained, offline-runnable suite.

Plug it into the evolution loop:

    from nyx.evolution.benchmarks import default_swebench_suite
    engine = EvolutionEngine(benchmark=default_swebench_suite())
    engine.evolve(generations=10)

With a real Ollama Cloud brain this produces a genuine correctness gradient
(better genomes → more tests pass). In deterministic MOCK mode the stub coder
emits a fixed ``feature`` implementation, so the suite yields a stable partial
score — useful to prove the harness executes generated code and scores it, but
the live brain is where evolution against this suite really bites.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..agents.base import Agent
from ..security.sandbox import run_sandboxed

_CODE_BLOCK = re.compile(r"```(?:python)?\s*\n(.*?)```", re.DOTALL)


def extract_code(text: str) -> str:
    """Pull the first fenced Python block; fall back to the raw text."""
    m = _CODE_BLOCK.search(text)
    return m.group(1).strip() if m else text.strip()


@dataclass
class BenchmarkTask:
    id: str
    prompt: str
    test_code: str          # asserts referencing the entrypoint
    entrypoint: str = "feature"
    timeout: float = 10.0


@dataclass
class TaskResult:
    id: str
    passed: bool
    detail: str = ""


@dataclass
class SuiteResult:
    results: list[TaskResult] = field(default_factory=list)

    @property
    def score(self) -> float:
        if not self.results:
            return 0.0
        return round(sum(1 for r in self.results if r.passed) / len(self.results), 4)


class SWEBenchSuite:
    """A callable benchmark: ``suite(agent) -> float`` (pass fraction)."""

    def __init__(self, tasks: list[BenchmarkTask]):
        self.tasks = tasks

    def evaluate(self, agent: Agent) -> SuiteResult:
        result = SuiteResult()
        for task in self.tasks:
            code = extract_code(agent.run(task.prompt).text)
            harness = (
                code
                + "\n\n# ---- hidden tests ----\n"
                + task.test_code
                + "\nprint('ALL_TESTS_PASSED')\n"
            )
            sb = run_sandboxed(harness, timeout=task.timeout)
            passed = sb.ok and "ALL_TESTS_PASSED" in sb.stdout
            detail = "ok" if passed else (sb.stderr.strip().splitlines()[-1:] or ["no output"])[0]
            result.results.append(TaskResult(id=task.id, passed=passed, detail=detail))
        return result

    def __call__(self, agent: Agent) -> float:
        return self.evaluate(agent).score


def default_swebench_suite() -> SWEBenchSuite:
    """A small, self-contained reference suite (entrypoint: ``feature``)."""
    return SWEBenchSuite(
        [
            BenchmarkTask(
                id="sum_list",
                prompt="Implement `feature(items)` that returns the sum of a list of numbers.",
                test_code="assert feature([1, 2, 3]) == 6\nassert feature([]) == 0",
            ),
            BenchmarkTask(
                id="validate_input",
                prompt="Implement `feature(items)` that sums numbers and raises ValueError on non-numbers.",
                test_code=(
                    "raised = False\n"
                    "try:\n"
                    "    feature(['x'])\n"
                    "except ValueError:\n"
                    "    raised = True\n"
                    "assert raised, 'expected ValueError on bad input'\n"
                    "assert feature([2, 2]) == 4"
                ),
            ),
            BenchmarkTask(
                id="product_list",
                prompt="Implement `feature(items)` that returns the product of a list of numbers.",
                test_code="assert feature([2, 3, 4]) == 24",
            ),
            BenchmarkTask(
                id="max_list",
                prompt="Implement `feature(items)` that returns the maximum value in a list.",
                test_code="assert feature([3, 9, 2]) == 9",
            ),
        ]
    )


def heldout_swebench_suite() -> SWEBenchSuite:
    """A **held-out** suite (distinct tasks) for standing evaluation, so the eval
    score is not contaminated by the tasks evolution trained on."""
    return SWEBenchSuite(
        [
            BenchmarkTask(
                id="ho_sum",
                prompt="Implement `feature(items)` that returns the total of a list of numbers.",
                test_code="assert feature([4, 5, 6]) == 15\nassert feature([]) == 0",
            ),
            BenchmarkTask(
                id="ho_sum_singleton",
                prompt="Implement `feature(items)` that returns the sum of the list.",
                test_code="assert feature([10]) == 10",
            ),
            BenchmarkTask(
                id="ho_min",
                prompt="Implement `feature(items)` that returns the minimum value in a list.",
                test_code="assert feature([3, 9, 2]) == 2",
            ),
            BenchmarkTask(
                id="ho_length",
                prompt="Implement `feature(items)` that returns the number of elements.",
                test_code="assert feature([1, 1, 1]) == 3",
            ),
        ]
    )
