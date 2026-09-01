"""SEC EDGAR tools — XBRL financials, filings, facts.

Wraps the ``edgartools`` library — the same engine behind the recommended
`sec-edgar-mcp <https://github.com/stefanoamorelli/sec-edgar-mcp>`_ server. We
use it **directly as a Python library** rather than spawning the MCP subprocess,
because NYX is itself a Python app — fewer moving parts, same data and precision.
To use the MCP server instead (filings, XBRL financials, Form 3/4/5 insider
trading, each with the source SEC URL), run ``nyx mcp-init`` to register it in
``.nyx/mcp.json`` and it becomes the ``mcp.sec-edgar-mcp`` tool.

Optional dependency: ``pip install "edgartools[ai]"`` and set
``EDGAR_IDENTITY="Your Name your.email@example.com"`` (SEC requires it). Without
the lib (or without network), each tool returns a clear, structured error so the
factory keeps running.
"""
from __future__ import annotations

import os

from .registry import ToolRegistry, ToolResult


def _ensure_edgar(identity: str):
    """Import edgartools and set the SEC identity, or raise a helpful error."""
    try:
        import edgar  # type: ignore
    except ImportError as exc:  # pragma: no cover - depends on optional install
        raise RuntimeError(
            "edgartools not installed. Run: pip install \"edgartools[ai]\" "
            "and set EDGAR_IDENTITY."
        ) from exc
    ident = identity or os.environ.get("EDGAR_IDENTITY", "")
    if not ident:
        raise RuntimeError("EDGAR_IDENTITY not set (SEC requires 'Name email').")
    edgar.set_identity(ident)
    return edgar


def register_edgar_tools(registry: ToolRegistry, *, identity: str = "") -> None:
    def edgar_financials(ticker: str) -> ToolResult:  # pragma: no cover - needs network/lib
        edgar = _ensure_edgar(identity)
        fin = edgar.Company(ticker).get_financials()
        data = {
            "ticker": ticker.upper(),
            "balance_sheet": str(fin.balance_sheet()),
            "income_statement": str(fin.income_statement()),
            "cash_flow": str(fin.cash_flow_statement()),
        }
        return ToolResult(ok=True, data=data)

    def edgar_filings(ticker: str, form: str = "10-K", limit: int = 5) -> ToolResult:  # pragma: no cover
        edgar = _ensure_edgar(identity)
        filings = edgar.Company(ticker).get_filings(form=form)
        rows = [{"form": f.form, "date": str(f.filing_date), "accession": f.accession_no}
                for f in list(filings)[:limit]]
        return ToolResult(ok=True, data={"ticker": ticker.upper(), "form": form, "filings": rows})

    def edgar_facts(ticker: str) -> ToolResult:  # pragma: no cover - needs network/lib
        edgar = _ensure_edgar(identity)
        facts = edgar.Company(ticker).get_facts()
        return ToolResult(ok=True, data={"ticker": ticker.upper(), "facts": str(facts)})

    from .registry import ArgSpec

    ticker = ArgSpec("ticker symbol", str, required=True, max_len=12, pattern=r"[A-Za-z.\-]{1,12}")
    registry.add("edgar_financials", "SEC XBRL financial statements for a ticker (balance sheet, "
                 "income, cash flow).", edgar_financials, {"ticker": ticker}, external=True)
    registry.add("edgar_filings", "List a company's SEC filings by form (10-K, 10-Q, 8-K, 4, 13F-HR).",
                 edgar_filings,
                 {"ticker": ticker, "form": ArgSpec("filing form", str, max_len=12),
                  "limit": ArgSpec("max rows", int)}, external=True)
    registry.add("edgar_facts", "All standardized XBRL facts for a ticker (for deep/footnote analysis).",
                 edgar_facts, {"ticker": ticker}, external=True)
