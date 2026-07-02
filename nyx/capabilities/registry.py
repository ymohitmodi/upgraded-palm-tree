"""Capability registry — discover and select the right goal handler.

Registered entries are capability *classes* (or zero-arg factories): ``get`` and
``select_for`` return a **fresh instance** each call, so per-run state (cached
benchmarks, fetch flags) never leaks between runs or configs.
"""
from __future__ import annotations

from typing import Callable

from .base import Capability

_REGISTRY: dict[str, Callable[[], Capability]] = {}


def register(capability: type[Capability] | Callable[[], Capability]) -> None:
    """Register a Capability class (or zero-arg factory)."""
    name = getattr(capability, "name", None)
    if not name or not isinstance(name, str):
        raise ValueError("capability must define a class-level `name`")
    _REGISTRY[name] = capability


def all_capabilities() -> list[Capability]:
    _ensure_builtin()
    return [factory() for factory in _REGISTRY.values()]


def get(name: str) -> Capability | None:
    _ensure_builtin()
    factory = _REGISTRY.get(name)
    return factory() if factory else None


def select_for(objective: str) -> Capability | None:
    """Pick the first registered capability that matches the objective."""
    _ensure_builtin()
    for name, factory in _REGISTRY.items():
        if name == "software":
            continue  # catch-all fallback goes last
        cap = factory()
        if cap.matches(objective):
            return cap
    fallback = _REGISTRY.get("software")
    return fallback() if fallback else None


def _ensure_builtin() -> None:
    """Register built-ins that aren't already present (idempotent, never
    suppressed by earlier custom registrations)."""
    from ..domains.investing.capability import ValueInvestingCapability
    from .software import SoftwareFactoryCapability

    for cls in (SoftwareFactoryCapability, ValueInvestingCapability):
        _REGISTRY.setdefault(cls.name, cls)
