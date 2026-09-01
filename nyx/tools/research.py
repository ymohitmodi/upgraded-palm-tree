"""Research tools — arXiv papers and recent news, for any long-running objective.

An advisor building an EB-1A case needs the publication landscape (who publishes
what, where, and when in AI security); an analyst needs the news flow. Both are
served by free, keyless endpoints, fetched through the same egress-guarded,
cached :class:`~nyx.tools.web.WebFetcher` as everything else:

- **arXiv** — the export API (``export.arxiv.org/api/query``) returns Atom XML;
  parsed here with a dependency-free reader (same approach as the news RSS
  parser). Allowlist ``arxiv.org,export.arxiv.org`` to use it under egress policy.
- **News** — Google News RSS via :mod:`nyx.domains.investing.news` (allowlist
  ``news.google.com``).

Both are *untrusted external content*: the registry injection-classifies their
output, and callers store results with ``trusted=False``.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import quote_plus

from .registry import ArgSpec, ToolRegistry, ToolResult

_ENTRY_RE = re.compile(r"<entry>(.*?)</entry>", re.DOTALL | re.IGNORECASE)
_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.DOTALL | re.IGNORECASE)
_SUMMARY_RE = re.compile(r"<summary[^>]*>(.*?)</summary>", re.DOTALL | re.IGNORECASE)
_ID_RE = re.compile(r"<id>(.*?)</id>", re.DOTALL | re.IGNORECASE)
_PUBLISHED_RE = re.compile(r"<published>(.*?)</published>", re.DOTALL | re.IGNORECASE)
_WS_RE = re.compile(r"\s+")


def _clean(text: str) -> str:
    text = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", text, flags=re.DOTALL)
    text = (text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
            .replace("&#39;", "'").replace("&quot;", '"'))
    return _WS_RE.sub(" ", text).strip()


@dataclass
class Paper:
    title: str
    url: str
    published: str
    summary: str


def arxiv_url(query: str, limit: int = 10, op: str = "AND") -> str:
    # Relevance-ranked with the meaningful terms AND-ed: a loose `all:` query
    # matches the wrong sense of common words ("cloud" → cosmic-ray papers), while
    # a strict phrase over-restricts. AND-ing up to five substantive terms returns
    # on-topic literature; op="OR" is the recall fallback when AND finds nothing.
    joiner = f"+{op}+"
    terms = [t for t in re.split(r"[^\w-]+", query) if len(t) > 2][:5]
    search = joiner.join(f"all:{quote_plus(t)}" for t in terms) or f"all:{quote_plus(query)}"
    return (f"https://export.arxiv.org/api/query?search_query={search}"
            f"&sortBy=relevance&sortOrder=descending&max_results={max(1, min(limit, 50))}")


def parse_arxiv_atom(xml: str, limit: int = 10) -> list[Paper]:
    """Parse an arXiv Atom feed into papers. Resilient: malformed input → []."""
    out: list[Paper] = []
    for block in _ENTRY_RE.findall(xml or ""):
        tm = _TITLE_RE.search(block)
        if not tm:
            continue
        title = _clean(tm.group(1))
        if not title:
            continue
        um = _ID_RE.search(block)
        sm = _SUMMARY_RE.search(block)
        pm = _PUBLISHED_RE.search(block)
        out.append(Paper(
            title=title,
            url=_clean(um.group(1)) if um else "",
            published=_clean(pm.group(1))[:10] if pm else "",
            summary=_clean(sm.group(1))[:400] if sm else "",
        ))
        if len(out) >= limit:
            break
    return out


def fetch_arxiv(fetcher, query: str, *, limit: int = 10) -> list[Paper]:  # pragma: no cover - live
    """Latest arXiv papers for a query, via the cached, allowlisted fetcher.

    Precision first (terms AND-ed), recall fallback (OR) when AND matches nothing
    — objective-derived queries often mix technical and case-specific words, and a
    zero-evidence radar is worse than a looser one. ``as_text=False`` keeps the
    raw Atom XML (the HTML→text reducer would strip the ``<entry>`` structure)."""
    for op in ("AND", "OR"):
        try:
            doc = fetcher.fetch(arxiv_url(query, limit, op=op), as_text=False)
        except Exception:  # noqa: BLE001 — a blocked/absent feed must not sink a run
            return []
        papers = parse_arxiv_atom(doc.text, limit=limit)
        if papers:
            return papers
    return []


def register_research_tools(registry: ToolRegistry, fetcher) -> None:
    """Register arxiv_search + news_search on the shared fetcher."""

    def arxiv_search(query: str, limit: int = 10) -> ToolResult:  # pragma: no cover - live
        papers = fetch_arxiv(fetcher, query, limit=limit)
        if not papers:
            return ToolResult(ok=False, error="no arXiv results (check allowlist: "
                                              "arxiv.org,export.arxiv.org)")
        body = "\n".join(f"- [{p.published}] {p.title} — {p.url}\n  {p.summary}"
                         for p in papers)
        return ToolResult(ok=True, data=body, meta={"results": len(papers)})

    def news_search(query: str, limit: int = 8) -> ToolResult:  # pragma: no cover - live
        from ..domains.investing.news import fetch_news

        headlines = fetch_news(fetcher, query, limit=limit)
        if not headlines:
            return ToolResult(ok=False, error="no news results (check allowlist: "
                                              "news.google.com)")
        body = "\n".join(f"- {h.title} ({h.published})" for h in headlines)
        return ToolResult(ok=True, data=body, meta={"results": len(headlines)})

    registry.add(
        "arxiv_search",
        "Search arXiv for recent papers on a topic (title, date, link, abstract) — "
        "for literature reviews, SoK pipelines, and tracking a research area.",
        arxiv_search,
        {"query": ArgSpec("topic or keywords", str, required=True, max_len=300),
         "limit": ArgSpec("max papers (default 10)", int)},
        external=True,
    )
    registry.add(
        "news_search",
        "Search recent news headlines on any topic (Google News RSS).",
        news_search,
        {"query": ArgSpec("topic or keywords", str, required=True, max_len=300),
         "limit": ArgSpec("max headlines (default 8)", int)},
        external=True,
    )
