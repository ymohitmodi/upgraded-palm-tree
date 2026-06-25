"""Capability registry — discover and select the right goal handler."""
from __future__ import annotations

from .base import Capability

_REGISTRY: dict[str, Capability] = {}


def register(capability: Capability) -> None:
    _REGISTRY[capability.name] = capability


def all_capabilities() -> list[Capability]:
    return list(_REGISTRY.values())


def get(name: str) -> Capability | None:
    return _REGISTRY.get(name)


def select_for(objective: str) -> Capability | None:
    """Pick the first registered capability that matches the objective."""
    _ensure_builtin()
    for cap in _REGISTRY.values():
        if cap.name != "software" and cap.matches(objective):
            return cap
    return _REGISTRY.get("software")


def _ensure_builtin() -> None:
    """Lazily register built-in capabilities (avoids import cycles)."""
    if _REGISTRY:
        return
    from ..domains.investing.capability import ValueInvestingCapability
    from .software import SoftwareFactoryCapability

    register(SoftwareFactoryCapability())
    register(ValueInvestingCapability())
