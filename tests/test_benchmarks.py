from __future__ import annotations

from nyx.agents.roles import build_agent
from nyx.constitution import Constitution
from nyx.evolution.benchmarks import default_swebench_suite, extract_code
from nyx.providers.mock import MockProvider


def test_extract_code_pulls_fenced_block():
    text = "blah\n```python\ndef f():\n    return 1\n```\ntail"
    assert extract_code(text) == "def f():\n    return 1"
    assert extract_code("no fences here") == "no fences here"


def test_swebench_runs_generated_code_in_sandbox(config, constitution_path):
    const = Constitution.load(constitution_path)
    agent = build_agent("coder", config, MockProvider(config), const)
    suite = default_swebench_suite()
    result = suite.evaluate(agent)
    # The harness actually executes the candidate code: the mock coder emits a
    # summing `feature`, so sum/validate pass and product/max fail -> 50%.
    ids_passed = {r.id for r in result.results if r.passed}
    assert "sum_list" in ids_passed
    assert "product_list" not in ids_passed
    assert 0.0 < result.score < 1.0


def test_swebench_is_callable_as_benchmark(config, constitution_path):
    const = Constitution.load(constitution_path)
    agent = build_agent("coder", config, MockProvider(config), const)
    score = default_swebench_suite()(agent)
    assert isinstance(score, float)
