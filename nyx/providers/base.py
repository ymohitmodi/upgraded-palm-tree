"""Provider abstraction.

A provider turns a list of chat messages into a completion. The factory only
ever talks to this interface, so the same agents run against Ollama Cloud, a
local Ollama, or the deterministic mock without changes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class ChatMessage:
    role: str  # system | user | assistant
    content: str


@dataclass
class Completion:
    text: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    raw: dict = field(default_factory=dict)
    # Structured tool calls the model requested (native function-calling). Each is
    # {"name": str, "arguments": dict}. Empty when the model answered in text.
    tool_calls: list = field(default_factory=list)

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


class Provider(Protocol):
    """The minimal contract every brain implements."""

    name: str

    def chat(
        self,
        model: str,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.2,
        max_tokens: int = 2048,
        tools: list | None = None,   # OpenAI-style tool schemas for function-calling
    ) -> Completion:
        ...
