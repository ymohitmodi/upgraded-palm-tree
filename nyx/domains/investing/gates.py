"""Investing constitution gates — values for an autonomous capital allocator.

Three domain rules NYX must not violate when acting as an investor:

1. **No guaranteed returns** — markets are uncertain; promising a return (or
   "risk-free" gains) is forbidden.
2. **No un-sourced numbers** — every financial figure must trace to a filing
   (LLMs hallucinate numbers; this gate rejects free-text figures).
3. **Margin of safety required** — a buy thesis without an explicit margin of
   safety / intrinsic-value comparison is rejected (capital preservation first).

These are exposed as (a) plain functions you can call anywhere, and (b) extra
``forbidden`` lines for the Constitution, enforced by its ``check_forbidden``.
"""
from __future__ import annotations

import re

from ...constitution import Constitution

INVESTING_FORBIDDEN = [
    "guarantee investment returns",
    "fabricate financial figures",
]

_GUARANTEE_RE = re.compile(
    r"\b(guarantee[d]?|risk[\s-]?free|can'?t lose|no risk)\b.*\b(return|profit|gain|money)\b",
    re.IGNORECASE,
)
_NUMBER_RE = re.compile(r"\$?\d[\d,]*(?:\.\d+)?\s*(?:%|bn|billion|m|million|x)?", re.IGNORECASE)
_SOURCE_RE = re.compile(r"\b(10-?k|10-?q|8-?k|sec|edgar|xbrl|filing|annual report|source:)\b", re.IGNORECASE)
_MOS_RE = re.compile(r"\b(margin of safety|intrinsic value|undervalued|discount to value)\b", re.IGNORECASE)
_BUY_RE = re.compile(r"\b(buy|invest|recommend|long|accumulate|shortlist|top pick)\b", re.IGNORECASE)


def guarantees_return(text: str) -> bool:
    return bool(_GUARANTEE_RE.search(text))


def has_unsourced_numbers(text: str) -> bool:
    """True if the text states financial figures without any source marker."""
    has_numbers = len(_NUMBER_RE.findall(text)) >= 3
    return has_numbers and not _SOURCE_RE.search(text)


def lacks_margin_of_safety(text: str) -> bool:
    """True if it recommends buying without invoking a margin of safety."""
    return bool(_BUY_RE.search(text)) and not _MOS_RE.search(text)


def check_investing(text: str) -> list[str]:
    """Return investing-gate violations for an analyst artifact."""
    v: list[str] = []
    if guarantees_return(text):
        v.append("G_NO_GUARANTEE: promises guaranteed/risk-free returns")
    if has_unsourced_numbers(text):
        v.append("G_SOURCED_NUMBERS: financial figures not traced to filings")
    if lacks_margin_of_safety(text):
        v.append("G_MARGIN_OF_SAFETY: buy thesis lacks an explicit margin of safety")
    return v


def investing_constitution(path: str | None = None, mode: str = "block") -> Constitution:
    """Load the base constitution and add the investing forbidden rules."""
    from ...config import load_config

    cfg = load_config()
    const = Constitution.load(path or cfg.constitution_path, mode=mode)
    for line in INVESTING_FORBIDDEN:
        if line not in const.forbidden:
            const.forbidden.append(line)
    return const
