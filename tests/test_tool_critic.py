"""Critic pass on tool outputs: flag results that don't support the goal."""
from __future__ import annotations

from nyx.agents.base import _assess_observation
from nyx.agents.roles import build_agent
from nyx.constitution import Constitution
from nyx.providers.base import Completion
from nyx.tools.registry import ArgSpec, ToolRegistry, ToolResult


def test_assess_observation_heuristics():
    assert _assess_observation("summarize the 10-K risk factors", "")[0] is False
    assert _assess_observation("x", "[tool error] boom")[0] is False
    # Short + off-topic → flagged.
    ok, why = _assess_observation("compute margin of safety for AAPL", "banana bread recipe")
    assert ok is False and why
    # Relevant, substantial → useful.
    ok, _ = _assess_observation(
        "compute margin of safety for AAPL",
        "AAPL margin of safety versus intrinsic value is 22% based on owner earnings.")
    assert ok is True


def _agent(config, constitution_path, provider):
    const = Constitution.load(constitution_path, mode=config.constitution_mode)
    return build_agent("advisor", config, provider, const)


def test_low_signal_tool_result_is_flagged_to_the_agent(config, constitution_path):
    """An off-topic tool result gets a [low-signal ...] caution fed back so the
    agent can verify/re-source instead of building on it."""
    class Provider:
        name = "p"
        def __init__(self):
            self.turn = 0
        def chat(self, model, messages, *, temperature=0.2, max_tokens=2048, tools=None):
            self.turn += 1
            if self.turn == 1:
                return Completion(text="", model=model,
                                  tool_calls=[{"name": "search", "arguments": {"q": "x"}}])
            joined = " ".join(m.content for m in messages)
            assert "[low-signal" in joined            # critic warned the agent
            return Completion(text="Re-sourced and answered.", model=model)

    agent = _agent(config, constitution_path, Provider())
    box = ToolRegistry()
    box.add("search", "search", lambda q: ToolResult(ok=True, data="unrelated cat video"),
            {"q": ArgSpec("query", str, required=True)})
    out = agent.run_with_tools("find AAPL free cash flow and margin of safety", box, max_steps=3)
    assert "Re-sourced" in out.text


def test_useful_tool_result_is_not_flagged(config, constitution_path):
    class Provider:
        name = "p"
        def __init__(self):
            self.turn = 0
        def chat(self, model, messages, *, temperature=0.2, max_tokens=2048, tools=None):
            self.turn += 1
            if self.turn == 1:
                return Completion(text="", model=model,
                                  tool_calls=[{"name": "sec", "arguments": {"t": "AAPL"}}])
            assert "[low-signal" not in " ".join(m.content for m in messages)
            return Completion(text="done", model=model)

    agent = _agent(config, constitution_path, Provider())
    box = ToolRegistry()
    box.add("sec", "sec facts", lambda t: ToolResult(
        ok=True, data="AAPL free cash flow 90B; margin of safety 20% vs intrinsic value."),
        {"t": ArgSpec("ticker", str, required=True)})
    out = agent.run_with_tools("find AAPL free cash flow and margin of safety", box, max_steps=3)
    assert out.text == "done"
