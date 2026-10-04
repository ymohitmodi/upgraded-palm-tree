"""Reasoning models return EMPTY content when the token budget dies mid-thought.

Left unhandled, every structured call site (router, injection classifier, factor
weights, analyst assessment) silently degrades to its fallback. The provider must
notice and retry with room to finish.
"""
from __future__ import annotations

from nyx.config import Config
from nyx.providers.base import ChatMessage
from nyx.providers.ollama_cloud import REASONING_RETRY_TOKENS, OllamaCloudProvider


def _response(content: str, finish_reason: str) -> dict:
    return {
        "choices": [{"message": {"role": "assistant", "content": content,
                                 "reasoning": "thinking..."},
                     "finish_reason": finish_reason}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 20},
    }


def _provider(monkeypatch, responses: list[dict]) -> tuple[OllamaCloudProvider, list[dict]]:
    provider = OllamaCloudProvider(Config(ollama_api_key="k"))
    sent: list[dict] = []

    def fake_post(payload):
        sent.append(payload)
        return responses[min(len(sent) - 1, len(responses) - 1)]

    monkeypatch.setattr(provider, "_post", fake_post)
    return provider, sent


def test_empty_content_from_truncated_reasoning_is_retried(monkeypatch):
    provider, sent = _provider(monkeypatch, [
        _response("", "length"),            # ran out of budget while reasoning
        _response("2,1,1,3", "stop"),       # given room, it answers
    ])
    out = provider.chat("m", [ChatMessage(role="user", content="hi")], max_tokens=20)
    assert out.text == "2,1,1,3"
    assert len(sent) == 2
    assert sent[0]["max_tokens"] == 20
    assert sent[1]["max_tokens"] == REASONING_RETRY_TOKENS


def test_empty_content_for_other_reasons_is_not_retried(monkeypatch):
    """finish_reason='stop' with empty content is a genuine empty answer, not truncation."""
    provider, sent = _provider(monkeypatch, [_response("", "stop")])
    out = provider.chat("m", [ChatMessage(role="user", content="hi")], max_tokens=20)
    assert out.text == ""
    assert len(sent) == 1                    # no wasted retry


def test_nonempty_answer_never_retries(monkeypatch):
    provider, sent = _provider(monkeypatch, [_response("done", "stop")])
    out = provider.chat("m", [ChatMessage(role="user", content="hi")], max_tokens=20)
    assert out.text == "done" and len(sent) == 1


def test_already_generous_budget_is_not_retried(monkeypatch):
    """A budget at/above the retry ceiling has already had room — don't pay twice."""
    provider, sent = _provider(monkeypatch, [_response("", "length")])
    out = provider.chat("m", [ChatMessage(role="user", content="hi")],
                        max_tokens=REASONING_RETRY_TOKENS)
    assert out.text == "" and len(sent) == 1
