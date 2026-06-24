"""The factory: pipeline orchestration and the fan-out swarm pattern."""
from __future__ import annotations

from .fanout import FanOut, FanOutResult
from .orchestrator import Factory, FactoryResult, StageResult

__all__ = ["FanOut", "FanOutResult", "Factory", "FactoryResult", "StageResult"]
