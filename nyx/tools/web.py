"""Web access — a polite, cached scraper NYX can use as a tool.

Design goals: be a *good citizen* and be *offline-safe for tests/CI*.

- **Polite**: declares a User-Agent, rate-limits per host, and honors an optional
  domain allowlist so the factory can't wander off-target.
- **Cached**: every fetch is stored on disk so re-reading a 10-K or a letter is
  free and deterministic, and reruns don't hammer the source.
- **Pluggable transport**: the actual network call is injected, so tests run with
  a fake transport and never touch the network. The default transport uses
  ``requests`` if installed, else stdlib ``urllib``.
- **Text extraction**: a tiny dependency-free HTML→text reducer so agents reason
  over content, not markup.
"""
from __future__ import annotations

import hashlib
import json
import re
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

from .registry import ToolResult

# transport(url, headers) -> (status_code, body_bytes, final_url)
Transport = Callable[[str, dict], "tuple[int, bytes, str]"]

_TAG_RE = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.DOTALL | re.IGNORECASE)
_ANYTAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"[ \t]*\n\s*\n\s*", re.MULTILINE)


def html_to_text(html: str) -> str:
    html = _TAG_RE.sub(" ", html)
    text = _ANYTAG_RE.sub(" ", html)
    text = (text.replace("&nbsp;", " ").replace("&amp;", "&")
            .replace("&lt;", "<").replace("&gt;", ">").replace("&#39;", "'"))
    text = re.sub(r"[ \t]{2,}", " ", text)
    return _WS_RE.sub("\n\n", text).strip()


def pdf_to_text(body: bytes) -> str:
    """Extract readable text from a PDF's bytes.

    Many primary sources (e.g. Berkshire's shareholder letters) are PDFs. Without
    this, ``body.decode("utf-8")`` yields binary garbage. Uses ``pypdf`` if
    installed; otherwise returns a clear, actionable placeholder rather than
    poisoning memory with undecodable bytes.
    """
    try:
        from io import BytesIO

        from pypdf import PdfReader
    except ImportError:
        return "[pdf not extracted — install pypdf: pip install pypdf]"
    try:
        reader = PdfReader(BytesIO(body))
        pages = [(p.extract_text() or "") for p in reader.pages]
    except Exception as exc:  # noqa: BLE001 — a malformed PDF must not sink a crawl
        return f"[pdf extraction failed: {exc}]"
    text = "\n\n".join(pages)
    return _WS_RE.sub("\n\n", text).strip()


def _default_transport(url: str, headers: dict) -> tuple[int, bytes, str]:
    try:
        import requests  # optional

        resp = requests.get(url, headers=headers, timeout=30)
        return resp.status_code, resp.content, resp.url
    except ImportError:
        import urllib.request

        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310 (allowlisted use)
            return r.status, r.read(), r.geturl()


@dataclass
class Document:
    url: str
    status: int
    text: str
    from_cache: bool = False


class WebFetcher:
    def __init__(
        self,
        cache_dir: str | Path = ".nyx/webcache",
        user_agent: str = "nyx-dark-factory/0.1",
        allowed_domains: tuple[str, ...] = (),
        rate_limit_seconds: float = 1.0,
        transport: Transport | None = None,
    ):
        self.cache = Path(cache_dir)
        self.cache.mkdir(parents=True, exist_ok=True)
        self.user_agent = user_agent
        self.allowed = tuple(d.lower() for d in allowed_domains)
        self.rate_limit = rate_limit_seconds
        self.transport = transport or _default_transport
        # Resolve DNS for the SSRF guard only on the real network (default
        # transport); an injected transport (tests/mocks) skips resolution.
        self._resolve_guard = transport is None
        self._last_hit: dict[str, float] = {}
        self._lock = threading.Lock()

    def _cache_path(self, url: str) -> Path:
        """Cache entries partitioned by host (webcache/<host>/<hash>.json), so the
        store is manageable: inspect, size, or clear one source without touching
        the rest (SEC frames vs prices vs news vs filings)."""
        h = hashlib.sha256(url.encode()).hexdigest()[:20]
        host = (urlparse(url).hostname or "unknown").lower()
        host = re.sub(r"[^a-z0-9.-]", "_", host) or "unknown"
        return self.cache / host / f"{h}.json"

    def _cache_read(self, url: str) -> dict | None:
        """Read a cached entry — partitioned path first, then the legacy flat
        layout (pre-partition caches stay warm; no mass re-fetch)."""
        h = hashlib.sha256(url.encode()).hexdigest()[:20]
        for path in (self._cache_path(url), self.cache / f"{h}.json"):
            if path.exists():
                try:
                    return json.loads(path.read_text(encoding="utf-8"))
                except ValueError:
                    continue
        return None

    def fetch(self, url: str, *, refresh: bool = False, as_text: bool = True) -> Document:
        # SSRF/egress policy: scheme + allowlist + no private/loopback/metadata
        # addresses. Raises EgressBlocked (a PermissionError) on violation.
        from ..security.egress import check_url

        check_url(url, self.allowed, resolve=self._resolve_guard)

        if not refresh:
            d = self._cache_read(url)
            if d is not None:
                return Document(url=d["url"], status=d["status"], text=d["text"],
                                from_cache=True)

        # Per-host rate limit (polite; lock-protected for concurrent crawls —
        # the slot is claimed inside the lock so parallel workers queue up).
        host = urlparse(url).hostname or ""
        with self._lock:
            wait = self.rate_limit - (time.time() - self._last_hit.get(host, 0.0))
            self._last_hit[host] = time.time() + max(0.0, wait)
        if wait > 0:
            time.sleep(wait)
        status, body, final_url = self.transport(url, {"User-Agent": self.user_agent})

        # PDFs (e.g. Berkshire letters) are binary — extract text, don't decode
        # the raw bytes into garbage.
        if body[:5] == b"%PDF-":
            text = pdf_to_text(body) if as_text else body.decode("latin-1", errors="replace")
        else:
            raw = body.decode("utf-8", errors="replace")
            text = html_to_text(raw) if (as_text and "<" in raw[:2000]) else raw
        # Only cache successful responses — a transient 4xx/5xx must not poison
        # the cache and mask the source forever.
        if 200 <= status < 300:
            cpath = self._cache_path(url)
            cpath.parent.mkdir(parents=True, exist_ok=True)
            cpath.write_text(
                json.dumps({"url": final_url, "status": status, "text": text}), encoding="utf-8"
            )
        return Document(url=final_url, status=status, text=text)

    def crawl(self, urls: list[str], *, max_workers: int = 8,
              refresh: bool = False) -> list[Document]:
        """Fetch many URLs concurrently (scalable mode). Per-host politeness is
        preserved — the rate limiter is shared and lock-protected — while
        different hosts proceed in parallel. Failures become status=0 docs so
        one bad URL never sinks the batch."""
        from concurrent.futures import ThreadPoolExecutor

        def one(url: str) -> Document:
            try:
                return self.fetch(url, refresh=refresh)
            except Exception as exc:  # noqa: BLE001 — batch must survive
                return Document(url=url, status=0, text=f"[crawl error] {exc}")

        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            return list(pool.map(one, urls))

    # -- as a tool ----------------------------------------------------------
    def as_tool_func(self):
        def web_fetch(url: str, refresh: bool = False) -> ToolResult:
            doc = self.fetch(url, refresh=refresh)
            ok = 200 <= doc.status < 300
            return ToolResult(
                ok=ok,
                data=doc.text if ok else "",
                error="" if ok else f"HTTP {doc.status}",
                meta={"url": doc.url, "from_cache": doc.from_cache, "chars": len(doc.text)},
            )

        return web_fetch
