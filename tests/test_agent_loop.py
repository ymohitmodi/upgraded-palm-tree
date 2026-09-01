"""Deeper agent loop: native function-calling, multi-call turns, error recovery."""
from __future__ import annotations

from nyx.agents.base import _tool_schemas
from nyx.agents.roles import build_agent
from nyx.constitution import Constitution
from nyx.providers.base import Completion
from nyx.tools.registry import ArgSpec, ToolRegistry, ToolResult


def _agent(config, constitution_path, provider):
    const = Constitution.load(constitution_path, mode=config.constitution_mode)
    return build_agent("advisor", config, provider, const)


def test_tool_schemas_are_openai_shaped_and_respect_allowlist():
    box = ToolRegistry()
    box.add("web_fetch", "fetch a url", lambda url: ToolResult(ok=True, data=url),
            {"url": ArgSpec("the url", str, required=True)}, external=True)
    box.add("secret_tool", "nope", lambda: ToolResult(ok=True, data="x"))
    box.set_allowed({"web_fetch"})
    schemas = _tool_schemas(box)
    names = {s["function"]["name"] for s in schemas}
    assert names == {"web_fetch"}                       # allowlist respected
    fn = schemas[0]["function"]
    assert fn["parameters"]["properties"]["url"]["type"] == "string"
    assert fn["parameters"]["required"] == ["url"]


def test_native_tool_calls_are_executed(config, constitution_path):
    """A provider that returns structured tool_calls (native function-calling)
    gets them executed and the result fed back — no text protocol needed."""
    class NativeProvider:
        name = "native"
        def __init__(self):
            self.turn = 0
        def chat(self, model, messages, *, temperature=0.2, max_tokens=2048, tools=None):
            self.turn += 1
            assert tools and tools[0]["type"] == "function"   # schemas were passed
            if self.turn == 1:
                return Completion(text="", model=model,
                                  tool_calls=[{"name": "web_fetch",
                                               "arguments": {"url": "https://x.test"}}])
            assert any("TOOL RESULT (web_fetch)" in m.content for m in messages)
            return Completion(text="Done, grounded in the page.", model=model)

    agent = _agent(config, constitution_path, NativeProvider())
    box = ToolRegistry()
    box.add("web_fetch", "fetch", lambda url: ToolResult(ok=True, data=f"page {url}"),
            {"url": ArgSpec("url", str, required=True)})
    out = agent.run_with_tools("research it", box, max_steps=3)
    assert "Done" in out.text


def test_multiple_tool_calls_in_one_turn(config, constitution_path):
    calls_made = []

    class MultiProvider:
        name = "multi"
        def __init__(self):
            self.turn = 0
        def chat(self, model, messages, *, temperature=0.2, max_tokens=2048, tools=None):
            self.turn += 1
            if self.turn == 1:
                return Completion(text="", model=model, tool_calls=[
                    {"name": "get", "arguments": {"k": "a"}},
                    {"name": "get", "arguments": {"k": "b"}},
                ])
            return Completion(text="combined", model=model)

    agent = _agent(config, constitution_path, MultiProvider())
    box = ToolRegistry()
    box.add("get", "get", lambda k: (calls_made.append(k), ToolResult(ok=True, data=k))[1],
            {"k": ArgSpec("key", str, required=True)})
    agent.run_with_tools("fetch a and b", box, max_steps=2)
    assert calls_made == ["a", "b"]                     # both executed in one turn


def test_error_recovery_feeds_error_then_recovers(config, constitution_path):
    class RecoveringProvider:
        name = "recover"
        def __init__(self):
            self.turn = 0
        def chat(self, model, messages, *, temperature=0.2, max_tokens=2048, tools=None):
            self.turn += 1
            if self.turn == 1:
                return Completion(text="", model=model,
                                  tool_calls=[{"name": "flaky", "arguments": {}}])
            if self.turn == 2:
                # The failure was fed back as an [error] observation.
                assert any("[error]" in m.content for m in messages)
                return Completion(text="Recovered without the tool.", model=model)
            return Completion(text="x", model=model)

    agent = _agent(config, constitution_path, RecoveringProvider())
    box = ToolRegistry()
    box.add("flaky", "always fails", lambda: ToolResult(ok=False, error="boom"))
    out = agent.run_with_tools("do it", box, max_steps=3)
    assert "Recovered" in out.text


def test_text_call_protocol_still_supported(config, constitution_path):
    class TextProvider:
        name = "text"
        def __init__(self):
            self.turn = 0
        def chat(self, model, messages, *, temperature=0.2, max_tokens=2048, tools=None):
            self.turn += 1
            if self.turn == 1:
                return Completion(text='CALL echo {"v": "hi"}', model=model)
            return Completion(text="final", model=model)

    agent = _agent(config, constitution_path, TextProvider())
    box = ToolRegistry()
    box.add("echo", "echo", lambda v: ToolResult(ok=True, data=v), {"v": ArgSpec("v", str)})
    out = agent.run_with_tools("echo hi", box, max_steps=3)
    assert out.text == "final"
