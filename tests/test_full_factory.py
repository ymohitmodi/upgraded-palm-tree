from __future__ import annotations

from nyx.agents.roles import build_agent
from nyx.constitution import Constitution
from nyx.context import digest_to_memory
from nyx.memory import MemoryStore
from nyx.providers.base import Completion
from nyx.tools.registry import ToolRegistry, ToolResult


def test_agent_tool_loop_calls_tool_then_answers(config, constitution_path):
    """A live-style model that emits CALL gets the tool result fed back, then answers."""
    const = Constitution.load(constitution_path, mode=config.constitution_mode)

    class ScriptedProvider:
        name = "scripted"
        def __init__(self):
            self.turn = 0
        def chat(self, model, messages, **kw):
            self.turn += 1
            if self.turn == 1:
                return Completion(text='CALL web_fetch {"url": "https://example.com"}', model=model)
            # Second turn must have received the tool result as a user message.
            assert any("TOOL RESULT" in m.content for m in messages)
            return Completion(text="Final answer grounded in the fetched page.", model=model)

    agent = build_agent("advisor", config, ScriptedProvider(), const)
    box = ToolRegistry()
    box.add("web_fetch", "fetch", lambda url: ToolResult(ok=True, data=f"page:{url}"),
            external=False)
    result = agent.run_with_tools("research X", box, max_steps=3)
    assert "Final answer" in result.text


def test_agent_tool_loop_degrades_to_single_shot_offline(config, constitution_path):
    """Mock provider emits no CALL → behaves like a normal single-shot run."""
    const = Constitution.load(constitution_path, mode=config.constitution_mode)
    from nyx.providers.mock import MockProvider

    agent = build_agent("advisor", config, MockProvider(config), const)
    box = ToolRegistry()
    box.add("web_fetch", "fetch", lambda url: ToolResult(ok=True, data="x"))
    out = agent.run_with_tools("plan my career", box)
    assert out.text and isinstance(out.text, str)


def test_tool_loop_respects_least_privilege(config, constitution_path):
    """A CALL to a tool outside the allowlist is denied, not executed."""
    const = Constitution.load(constitution_path, mode=config.constitution_mode)

    class Caller:
        name = "caller"
        def __init__(self):
            self.turn = 0
        def chat(self, model, messages, **kw):
            self.turn += 1
            if self.turn == 1:
                return Completion(text='CALL edgar_facts {"ticker": "AAPL"}', model=model)
            joined = " ".join(m.content for m in messages)
            assert "not permitted" in joined      # denial fed back to the model
            return Completion(text="Understood, proceeding without it.", model=model)

    agent = build_agent("advisor", config, Caller(), const)
    box = ToolRegistry()
    box.add("edgar_facts", "sec", lambda ticker: ToolResult(ok=True, data=ticker))
    box.set_allowed({"web_fetch"})              # edgar not permitted
    result = agent.run_with_tools("do research", box, max_steps=3)
    assert "proceeding" in result.text


def test_full_10k_digested_into_memory(tmp_path, config):
    """Reading a full filing writes a recallable research memory (the learn loop)."""
    store = MemoryStore(tmp_path / "m.jsonl")
    text = "\n\n".join(
        [f"Item {i}. Routine language. " * 20 for i in range(30)]
        + ["Footnote 12: material lease obligation of $4.2B due 2027; going concern risk."])
    digest = digest_to_memory(store, text, source="AAPL 10-K",
                              tags=["sec", "aapl", "10-k"], config=config)
    assert digest.n_chunks > 3
    research = [le for le in store.all() if le.kind == "research"]
    assert research and "AAPL 10-K" in research[0].source
    # The digest is now recallable when reasoning about this company later.
    hits = store.recall("what are AAPL's lease obligations and going concern risks")
    assert hits
