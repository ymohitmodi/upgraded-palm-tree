"""Recent-news research for the value investor (Google News RSS — free, no key).

The objective says "research recent news; discount hype", so the analyst needs a
current-events signal alongside the filings. Google News exposes a keyword RSS
feed that needs no API key. We fetch it through the same egress-guarded, cached
``WebFetcher`` the rest of NYX uses (so ``news.google.com`` must be allowlisted),
and parse headlines with a dependency-free regex reader.

The feed is *untrusted* external content: headlines can be adversarial (pump
narratives, prompt-injection). Callers store the result as untrusted memory
(``trusted=False``) so it is injection-classified and never treated as doctrine.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import quote_plus

_ITEM_RE = re.compile(r"<item>(.*?)</item>", re.DOTALL | re.IGNORECASE)
_TITLE_RE = re.compile(r"<title>(.*?)</title>", re.DOTALL | re.IGNORECASE)
_DATE_RE = re.compile(r"<pubDate>(.*?)</pubDate>", re.DOTALL | re.IGNORECASE)


def _unescape(text: str) -> str:
    text = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", text, flags=re.DOTALL)
    return (text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
            .replace("&#39;", "'").replace("&quot;", '"').replace("&apos;", "'")).strip()


@dataclass
class Headline:
    title: str
    published: str


def parse_news_rss(xml: str, limit: int = 8) -> list[Headline]:
    """Parse a Google News RSS document into recent headlines (newest first as
    served). Resilient: a malformed feed yields an empty list, never an error."""
    out: list[Headline] = []
    for block in _ITEM_RE.findall(xml or ""):
        tm = _TITLE_RE.search(block)
        if not tm:
            continue
        dm = _DATE_RE.search(block)
        title = _unescape(tm.group(1))
        if title:
            out.append(Headline(title=title, published=_unescape(dm.group(1)) if dm else ""))
        if len(out) >= limit:
            break
    return out


def news_url(query: str) -> str:
    return ("https://news.google.com/rss/search?q="
            f"{quote_plus(query)}&hl=en-US&gl=US&ceid=US:en")


def fetch_news(fetcher, query: str, *, limit: int = 8) -> list[Headline]:  # pragma: no cover - live
    """Fetch recent headlines for ``query`` via the cached, allowlisted fetcher.

    ``as_text=False`` keeps the raw RSS/XML — the fetcher's HTML→text reducer would
    otherwise strip the ``<item>`` structure the parser needs."""
    try:
        doc = fetcher.fetch(news_url(query), as_text=False)
    except Exception:  # noqa: BLE001 — a blocked/absent feed must not sink a run
        return []
    return parse_news_rss(doc.text, limit=limit)
