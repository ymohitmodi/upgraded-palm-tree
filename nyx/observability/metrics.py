"""Lightweight in-memory metrics for a factory run.

Tracks the numbers a solo operator actually watches: model calls, tokens, an
approximate cost, gate pass-rate, and fan-out selection — operational excellence
without a metrics stack on the mini-PC.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Metrics:
    calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    gates_passed: int = 0
    gates_blocked: int = 0
    candidates_generated: int = 0
    stages: dict[str, float] = field(default_factory=dict)

    # Rough blended cost per 1K tokens (USD); Ollama Cloud bills by GPU-time,
    # this is a planning estimate only.
    cost_per_1k_tokens: float = 0.0008

    def record_call(self, prompt_tokens: int, completion_tokens: int) -> None:
        self.calls += 1
        self.prompt_tokens += prompt_tokens
        self.completion_tokens += completion_tokens

    def record_gate(self, passed: bool) -> None:
        if passed:
            self.gates_passed += 1
        else:
            self.gates_blocked += 1

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    @property
    def est_cost_usd(self) -> float:
        return round(self.total_tokens / 1000 * self.cost_per_1k_tokens, 4)

    @property
    def gate_pass_rate(self) -> float:
        total = self.gates_passed + self.gates_blocked
        return round(self.gates_passed / total, 3) if total else 1.0

    def summary(self) -> dict:
        return {
            "calls": self.calls,
            "total_tokens": self.total_tokens,
            "est_cost_usd": self.est_cost_usd,
            "candidates_generated": self.candidates_generated,
            "gate_pass_rate": self.gate_pass_rate,
            "gates_passed": self.gates_passed,
            "gates_blocked": self.gates_blocked,
        }
