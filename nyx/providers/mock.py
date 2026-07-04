"""Deterministic mock provider.

When no ``OLLAMA_API_KEY`` is configured, the factory still needs a brain so the
entire architecture — pipeline, gates, fan-out, evolution, audit — is runnable
and testable offline and in CI. This provider produces deterministic,
role-appropriate artifacts seeded by the request content and temperature, so
fan-out yields distinct candidates and evolution can score real differences.

It is intentionally not "smart"; it is a faithful stand-in for the shape of a
real completion.
"""
from __future__ import annotations

import hashlib
import re

from ..config import Config
from .base import ChatMessage, Completion


def _seed(*parts: str) -> int:
    h = hashlib.sha256("||".join(parts).encode("utf-8")).hexdigest()
    return int(h[:8], 16)


def _role_of(messages: list[ChatMessage]) -> str:
    for m in messages:
        if m.role == "system":
            match = re.search(r"ROLE=([a-z_]+)", m.content)
            if match:
                return match.group(1)
    return "generic"


def _topic_of(messages: list[ChatMessage]) -> str:
    for m in reversed(messages):
        if m.role == "user":
            for line in m.content.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    return line[:120]
    return "the task"


class MockProvider:
    name = "mock"

    def __init__(self, config: Config | None = None):
        self.config = config

    def chat(
        self,
        model: str,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.2,
        max_tokens: int = 2048,
    ) -> Completion:
        role = _role_of(messages)
        topic = _topic_of(messages)
        # Fold the system prompt (which carries the agent's evolvable charter)
        # into the seed so prompt mutations produce different artifacts.
        system = next((m.content for m in messages if m.role == "system"), "")
        sys_hash = hashlib.sha256(system.encode("utf-8")).hexdigest()[:6]
        seed = _seed(role, topic, f"{temperature:.2f}", model, sys_hash)
        text = _render(role, topic, seed, temperature)
        return Completion(
            text=text,
            model=f"mock::{model}",
            prompt_tokens=sum(len(m.content) for m in messages) // 4,
            completion_tokens=len(text) // 4,
            raw={"mock": True, "role": role, "seed": seed},
        )


def _render(role: str, topic: str, seed: int, temperature: float) -> str:
    variant = seed % 3
    if role == "planner":
        # Deterministic backlog decomposition of the objective.
        facets = [
            "core flow", "data model + persistence", "input validation & errors",
            "observability (logs+metrics)", "tests & acceptance", "polish & docs",
        ]
        n = 3 + (seed % 3)  # 3..5 features
        lines = [f"- {topic}: {facets[i % len(facets)]}" for i in range(n)]
        return "\n".join(lines)
    if role == "explorer":
        return (
            f"# Opportunity brief: {topic}\n"
            f"Problem: users lack a reliable way to {topic.lower()}.\n"
            f"Target user: solo operators and small teams.\n"
            f"Why now: agentic tooling makes this 3-5x cheaper to build.\n"
            f"Riskiest assumption (variant {variant}): demand exists at this price."
        )
    if role == "architect":
        return (
            f"# Spec: {topic}\n"
            f"## Acceptance criteria\n"
            f"- AC1: the core flow for '{topic}' works end to end\n"
            f"- AC2: inputs are validated; errors are handled gracefully\n"
            f"- AC3: actions are observable (logs + metrics)\n"
            f"## Non-goals\n- Not building auth/billing in this increment\n"
            f"## Design (variant {variant})\n"
            f"- Module: service layer + thin adapter; idempotent operations\n"
            f"- Data: append-only event log for auditability\n"
            f"HAS_SPEC=true"
        )
    if role == "coder":
        # Slightly different implementations per variant so fan-out differs.
        bodies = [
            "    return sum(items)",
            "    total = 0\n    for it in items:\n        total += it\n    return total",
            "    import functools, operator\n"
            "    return functools.reduce(operator.add, items, 0)",
        ]
        return (
            f"# Implementation candidate (variant {variant}, temp {temperature:.2f})\n"
            f"```python\n"
            f"def feature(items):\n"
            f'    """Implements: {topic}."""\n'
            f"    if not all(isinstance(i, (int, float)) for i in items):\n"
            f"        raise ValueError('invalid input')  # input validation (C3)\n"
            f"{bodies[variant]}\n"
            f"```\n"
            f"No secrets in code. Inputs validated."
        )
    if role == "reviewer":
        score = 0.7 + (variant * 0.1)
        return (
            f"# Review of: {topic}\n"
            f"- Correctness: looks correct for the spec\n"
            f"- Security: no secrets, inputs validated (C3 ok), injection N/A\n"
            f"- Readability: clear\n"
            f"SECURITY_OK=true\n"
            f"SCORE={score:.2f}"
        )
    if role == "tester":
        return (
            f"# Tests for: {topic}\n"
            f"```python\n"
            f"def test_feature_happy(): assert feature([1,2,3]) == 6\n"
            f"def test_feature_validates():\n"
            f"    import pytest\n"
            f"    with pytest.raises(ValueError): feature(['x'])\n"
            f"```\n"
            f"TESTS_PASS=true"
        )
    if role == "deployer":
        return (
            f"# Release plan: {topic}\n"
            f"- Strategy: blue/green, single click rollback\n"
            f"- Reversible: yes (previous revision retained)\n"
            f"- Gate: requires operator approval at 'supervised'\n"
            f"DEPLOY_REVERSIBLE=true"
        )
    if role == "operator":
        return (
            f"# Operations report: {topic}\n"
            f"- Health: green; p99 latency nominal\n"
            f"- Alerts wired; runbook attached\n"
            f"- Action + rationale recorded to ledger\n"
            f"AUDITED=true"
        )
    if role == "security":
        return (
            f"# Security review: {topic}\n"
            f"- Secret scan: clean\n"
            f"- Prompt-injection surfaces: external input treated as data\n"
            f"- Threat model: least privilege, fail closed\n"
            f"SECURITY_OK=true"
        )
    return f"Acknowledged: {topic} (variant {variant})."
