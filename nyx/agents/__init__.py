"""The agent workforce — role-specialized, constitution-bound, evolvable."""
from __future__ import annotations

from .base import Agent, AgentResult, Genome
from .roles import (
    ArchitectAgent,
    CoderAgent,
    DeployerAgent,
    ExplorerAgent,
    OperatorAgent,
    PlannerAgent,
    ReviewerAgent,
    SecurityAgent,
    TesterAgent,
    ROLE_REGISTRY,
    build_agent,
)

__all__ = [
    "Agent",
    "AgentResult",
    "Genome",
    "PlannerAgent",
    "ExplorerAgent",
    "ArchitectAgent",
    "CoderAgent",
    "ReviewerAgent",
    "TesterAgent",
    "DeployerAgent",
    "OperatorAgent",
    "SecurityAgent",
    "ROLE_REGISTRY",
    "build_agent",
]
