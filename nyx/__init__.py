"""NYX — the autonomous dark factory.

A constitutional, self-evolving, multi-agent software factory that runs on an
Ollama Cloud brain from a single Windows 11 mini-PC.

Public surface is intentionally small; compose the factory via :class:`Factory`.
"""
from __future__ import annotations

__version__ = "0.1.0"

from .capabilities import CapabilityRunner, RunReport, select_for
from .config import Config, load_config
from .constitution import Constitution
from .factory.orchestrator import Factory, FactoryResult
from .memory import MemoryStore, reflect_on_run

__all__ = [
    "__version__",
    "Config",
    "load_config",
    "Constitution",
    "Factory",
    "FactoryResult",
    "CapabilityRunner",
    "RunReport",
    "select_for",
    "MemoryStore",
    "reflect_on_run",
]
