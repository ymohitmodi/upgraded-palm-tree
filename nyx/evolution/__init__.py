"""Self-evolving agents — a Darwin-Gödel style archive and evolution loop."""
from __future__ import annotations

from .archive import Archive, GenomeRecord
from .engine import EvolutionEngine, EvolutionReport

__all__ = ["Archive", "GenomeRecord", "EvolutionEngine", "EvolutionReport"]
