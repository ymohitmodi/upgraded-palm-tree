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

import json
import os
from dataclasses import dataclass, field

MCP_EDGAR = "mcp.edgartools"

# Every footnote topic is read for every company (no rotation, nothing skipped).
FOOTNOTE_TOPICS = ["debt", "leases", "litigation", "income taxes",
                   "commitments and contingencies", "revenue recognition"]

# Great capital allocators whose 13F holdings are worth cross-referencing.
DEFAULT_13F_MANAGERS = ("BRK-B",)


def readable(payload: str, limit: int = 1400) -> str:
    """Flatten a JSON tool payload into compact ``key: value`` lines.

    MCP tools return ``{"success": true, "data": {...}}`` — storing that raw fills
    memory with brace scaffolding that embeds poorly and reads worse. This renders
    the ``data`` subtree as one readable line per scalar (lists inlined, empties
    dropped), so a remembered lesson is prose-like evidence, not wire format.
    Non-JSON input passes through untouched.
    """
    try:
        obj = json.loads(payload)
    except (ValueError, TypeError):
        return payload[:limit]
    if isinstance(obj, dict):
        obj = obj.get("data", obj)
    lines: list[str] = []

    def walk(prefix: str, value, depth: int) -> None:
        if len(lines) >= 60 or depth > 4:
            return
        if isinstance(value, dict):
            for k, v in value.items():
                walk(f"{prefix}{k}." if prefix else f"{k}.", v, depth + 1) \
                    if isinstance(v, (dict, list)) else walk(f"{prefix}{k}", v, depth + 1)
        elif isinstance(value, list):
            scalars = [str(v) for v in value if not isinstance(v, (dict, list))][:12]
            if scalars:
                lines.append(f"{prefix.rstrip('.')}: {', '.join(scalars)}")
            for item in value[:8]:
                if isinstance(item, (dict, list)):
                    walk(prefix, item, depth + 1)
        else:
            if value not in (None, "", [], {}):
                lines.append(f"{prefix.rstrip('.')}: {value}")

    walk("", obj, 0)
    return ("\n".join(lines) or payload)[:limit]


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
            # Flatten JSON wire format into prose-like lines: the long-document
            # reader chunks/embeds this, and readable text retrieves far better.
            body = readable(result.data, limit=len(result.data))
            parts.append(f"## {name}\n{body}")
            read.sections[name] = len(body)

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


def read_full_10k(ticker: str, *, identity: str = "") -> str:  # pragma: no cover - live only
    """The full narrative text of a company's latest 10-K — Business, Risk Factors,
    MD&A, and notes — straight from edgartools (hundreds of KB, not a summary).

    This is the raw document NYX's long-document reader is built for: too large for
    any context window, so it is chunked, folded, and embedded rather than truncated.
    """
    try:
        import edgar  # type: ignore
    except ImportError:
        return ""
    ident = identity or os.environ.get("EDGAR_IDENTITY", "")
    if not ident:
        return ""
    try:
        edgar.set_identity(ident)
        tenk = edgar.Company(ticker).latest_tenk
        if tenk is None:
            return ""
        parts: list[str] = []
        # Every item of the report (Item 1 Business … Item 15 Exhibits), so the
        # WHOLE 10-K is read — the long-document engine bounds it by chunking, so
        # length is not a limit. Fall back to the main narrative accessors if the
        # item index is unavailable.
        items = list(getattr(tenk, "items", []) or [])
        for item in items:
            try:
                text = str(tenk[item] or "").strip()
            except Exception:  # noqa: BLE001 — a missing item must not sink the read
                text = ""
            if len(text) > 40:
                parts.append(f"{item}\n{text}")
        if not parts:
            for section in ("business", "risk_factors", "management_discussion"):
                try:
                    text = str(getattr(tenk, section) or "").strip()
                except Exception:  # noqa: BLE001
                    text = ""
                if len(text) > 40:
                    parts.append(text)
        return "\n\n".join(parts)
    except Exception:  # noqa: BLE001 — no 10-K / parse failure → empty, never fatal
        return ""


def multiyear_financials(ticker: str, *, identity: str = "",
                         years: int = 4) -> str:  # pragma: no cover - live only
    """Compact multi-year statement history (revenue, net income, assets, equity,
    cash flow) from the last ``years`` annual filings — the trend that reveals
    whether a moat is widening, holding, or eroding versus a single snapshot."""
    try:
        import edgar  # type: ignore
    except ImportError:
        return ""
    ident = identity or os.environ.get("EDGAR_IDENTITY", "")
    if not ident:
        return ""
    try:
        edgar.set_identity(ident)
        company = edgar.Company(ticker)
        filings = company.get_filings(form="10-K")
        rows: list[str] = []
        for filing in list(filings)[:years]:
            try:
                fin = filing.obj().financials
                fy = str(getattr(filing, "filing_date", ""))[:4]
                def g(getter):
                    try:
                        return float(getattr(fin, getter)() or 0) / 1e9
                    except Exception:  # noqa: BLE001
                        return 0.0
                rows.append(
                    f"FY~{fy}: revenue ${g('get_revenue'):.2f}B, net income "
                    f"${g('get_net_income'):.2f}B, assets ${g('get_total_assets'):.2f}B, "
                    f"equity ${g('get_stockholders_equity'):.2f}B, capex "
                    f"${abs(g('get_capital_expenditures')):.2f}B")
            except Exception:  # noqa: BLE001 — one bad filing must not sink the trend
                continue
        return "MULTI-YEAR TREND (newest first):\n" + "\n".join(rows) if rows else ""
    except Exception:  # noqa: BLE001
        return ""


_COMPANY_FOCUS = ("this company's durable competitive moat and how it is widening or "
                  "narrowing versus competitors, the quality and trend of its "
                  "owner-earnings, balance-sheet and footnote risks, management's "
                  "capital allocation, and whether it can compound for years")


def ingest_full_10k(memory, ticker: str, *, identity: str = "",
                    config=None, provider=None):  # pragma: no cover - live only
    """Read a company's ENTIRE latest 10-K (plus a multi-year statement trend) and
    INTERPRET it — extracting moat/risk/quality insights, not just a synthesis dump.
    Returns the digest or None."""
    from ...context import read_and_learn

    text = read_full_10k(ticker, identity=identity)
    if len(text) < 500:
        return None
    trend = multiyear_financials(ticker, identity=identity)
    if trend:
        text = f"{trend}\n\n{text}"
    focus = f"{ticker} — {_COMPANY_FOCUS}"
    digest, _, _ = read_and_learn(
        memory, text, source=f"10-K:{ticker}",
        tags=["sec", ticker.lower(), "10-k", "full-read", "footnotes", "multi-year"],
        focus=focus, config=config, provider=provider, doctrine=False, max_lessons=6)
    return digest


def ingest_company_filings(memory, toolbox, ticker: str, *,
                           config=None, provider=None):  # pragma: no cover - live only
    """Read one company's filings and INTERPRET them into moat/risk/quality insights
    (untrusted, company-specific), not a raw synthesis.

    Returns the :class:`DocumentDigest` (chunks stay embedded for detail lookups)
    or ``None``. Pass ``config``/``provider`` for live interpretation; omit for the
    free deterministic fold (every chunk still read + indexed either way)."""
    from ...context import read_and_learn

    read = fetch_company_filings(toolbox, ticker)
    if not read.ok:
        return None
    digest, _, _ = read_and_learn(
        memory, read.text, source=f"sec-filings:{ticker}",
        tags=["sec", ticker.lower(), "filings", "deep-read", "footnotes"],
        focus=f"{ticker} — {_COMPANY_FOCUS}", config=config, provider=provider,
        doctrine=False, max_lessons=5)
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
