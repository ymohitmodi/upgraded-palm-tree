"""Deep-value investing domain — aim NYX at finding undervalued public companies."""
from __future__ import annotations

from .backtest import (
    INVESTING_DIRECTIVES,
    Company,
    Universe,
    ValueBenchmark,
    default_universe,
)
from .data import (
    DataUnavailable,
    build_universe,
    build_universes,
    parse_stooq_csv,
    try_build_universes,
)
from .buffett import (
    PRINCIPLES,
    fetch_letters,
    letter_urls,
    seed_principles,
)
from .gates import check_investing, investing_constitution

__all__ = [
    "PRINCIPLES", "seed_principles", "letter_urls", "fetch_letters",
    "ValueBenchmark", "Universe", "Company", "default_universe", "INVESTING_DIRECTIVES",
    "check_investing", "investing_constitution",
    "DataUnavailable", "build_universe", "build_universes", "parse_stooq_csv",
    "try_build_universes",
]
