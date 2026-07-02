"""LLM-driven capability routing — no rule-based dispatch when a brain is live.

`route()` asks the model which registered capability best serves the objective,
constrained to the registry's names. Keyword `matches()` heuristics remain only
as the deterministic fallback for MOCK/offline mode and for parse failures, so
tests stay reproducible while production routing is genuinely semantic.
"""
from __future__ import annotations

from ..config import Config
from ..providers.base import ChatMessage, Provider
from .base import Capability
from .registry import all_capabilities, get, select_for


def route(objective: str, config: Config, provider: Provider) -> Capability:
    """Pick the capability for an objective — semantically when live."""
    caps = all_capabilities()
    if not config.mock_mode:
        catalog = "\n".join(f"- {c.name}: {c.description}" for c in caps)
        prompt = (
            "Pick the single best capability for this objective.\n"
            f"OBJECTIVE: {objective}\n\nCAPABILITIES:\n{catalog}\n\n"
            "Reply with ONLY the capability name, nothing else."
        )
        try:
            completion = provider.chat(
                config.model("fast"),
                [ChatMessage(role="user", content=prompt)],
                temperature=0.0,
                max_tokens=20,
            )
            name = completion.text.strip().splitlines()[0].strip("`'\" .").lower()
            chosen = get(name)
            if chosen is not None:
                return chosen
        except Exception:  # noqa: BLE001 — routing must never crash a run
            pass
    return select_for(objective)
