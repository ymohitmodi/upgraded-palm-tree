"""Deep SEC reading — every company's filings, read whole, nothing truncated.

The factor model only ever saw XBRL numbers and a price. This module gives the
analyst the *narrative* record too, for **every** company in the universe:

- **Footnotes** (all topics, not a rotating sample) — where the real economics
  hide: debt, leases, litigation, taxes, contingencies, revenue recognition.
- **8-K** material events and **Form 4** insider transactions.
- **13F** — note that *companies do not file 13F; institutions do*. So the useful
  signal is inverted: read a bellwether investor's 13F and ask which of our
  candidates they actually own. That comes straight from the filing's infotable.

Nothing is truncated. Each company's raw filing text is handed to the long-document
engine (:func:`nyx.context.digest_to_memory`), which chunks it, folds every chunk
into a bounded running synthesis, embeds each chunk for later retrieval, and
injection-screens the result before storing it as *untrusted* research memory.
So the whole document is read and indexed, while context stays bounded.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

MCP_EDGAR = "mcp.edgartools"

# Every footnote topic is read for every company (no rotation, nothing skipped).
FOOTNOTE_TOPICS = ["debt", "leases", "litigation", "income taxes",
                   "commitments and contingencies", "revenue recognition"]

# Great capital allocators whose 13F holdings are worth cross-referencing.
DEFAULT_13F_MANAGERS = ("BRK-B",)


@dataclass
class FilingRead:
    ticker: str
    text: str = ""
    sections: dict = field(default_factory=dict)   # section name -> chars read

    @property
    def ok(self) -> bool:
        return bool(self.text.strip())


def fetch_company_filings(toolbox, ticker: str) -> FilingRead:  # pragma: no cover - live only
    """Pull a company's full SEC surface via the edgartools MCP server.

    Every response is kept in full — truncation happens nowhere here; bounding is
    the long-document reader's job, and it bounds by *summarizing*, not by cutting.
    """
    read = FilingRead(ticker=ticker)
    parts: list[str] = []

    def _add(name: str, result) -> None:
        if result is not None and result.ok and isinstance(result.data, str) and result.data.strip():
            parts.append(f"## {name}\n{result.data}")
            read.sections[name] = len(result.data)

    for topic in FOOTNOTE_TOPICS:
        _add(f"Footnotes — {topic}",
             toolbox.call(MCP_EDGAR, tool="edgar_notes",
                          arguments={"identifier": ticker, "topic": topic}))
    _add("Recent 8-K events",
         toolbox.call(MCP_EDGAR, tool="edgar_filing",
                      arguments={"identifier": ticker, "form": "8-K"}))
    _add("Insider transactions (Form 4)",
         toolbox.call(MCP_EDGAR, tool="edgar_ownership",
                      arguments={"identifier": ticker, "analysis_type": "insiders", "limit": 20}))
    read.text = "\n\n".join(parts)
    return read


def ingest_company_filings(memory, toolbox, ticker: str, *,
                           config=None, provider=None):  # pragma: no cover - live only
    """Read one company's filings end-to-end into long-term research memory.

    Returns the :class:`DocumentDigest` (whose chunks stay embedded for detail
    lookups) or ``None`` when nothing could be read. Pass ``config``/``provider``
    to distill with the live model; omit them for the free, deterministic
    extractive fold (every chunk is still read and indexed either way)."""
    from ...context import digest_to_memory

    read = fetch_company_filings(toolbox, ticker)
    if not read.ok:
        return None
    digest = digest_to_memory(
        memory, read.text, source=f"sec-filings:{ticker}",
        tags=["sec", ticker.lower(), "filings", "deep-read", "footnotes"],
        config=config, provider=provider,
    )
    return digest


# -- 13F: which of our candidates do great investors actually own? -------------
def _managers_from_env() -> tuple[str, ...]:
    raw = os.environ.get("NYX_13F_MANAGERS", "")
    picked = tuple(t.strip().upper() for t in raw.split(",") if t.strip())
    return picked or DEFAULT_13F_MANAGERS


def read_13f_holdings(manager: str, *, identity: str = "") -> dict[str, float]:  # pragma: no cover - live
    """Return ``{ticker: position value}`` from a manager's latest 13F-HR infotable.

    Read straight from edgartools (the MCP tool reports a holdings *count* but not
    the positions). Multiple rows per issuer are summed. Any failure yields ``{}``
    so a missing filing never sinks a run."""
    try:
        import edgar  # type: ignore
    except ImportError:
        return {}
    ident = identity or os.environ.get("EDGAR_IDENTITY", "")
    if not ident:
        return {}
    try:
        edgar.set_identity(ident)
        filings = edgar.Company(manager).get_filings(form="13F-HR")
        if not filings:
            return {}
        table = filings[0].obj().infotable
        holdings: dict[str, float] = {}
        for ticker, value in zip(table["Ticker"], table["Value"]):
            key = str(ticker or "").strip().upper()
            if not key or key == "NAN":
                continue
            try:
                holdings[key] = holdings.get(key, 0.0) + float(value or 0)
            except (TypeError, ValueError):
                continue
        return holdings
    except Exception:  # noqa: BLE001 — a bad/absent 13F must never be fatal
        return {}


def bellwether_holdings(*, identity: str = "",
                        managers: tuple[str, ...] | None = None) -> dict[str, list[str]]:  # pragma: no cover - live
    """``{ticker: [managers holding it]}`` across the configured 13F filers."""
    owners: dict[str, list[str]] = {}
    for manager in (managers or _managers_from_env()):
        for ticker in read_13f_holdings(manager, identity=identity):
            owners.setdefault(ticker, []).append(manager)
    return owners
