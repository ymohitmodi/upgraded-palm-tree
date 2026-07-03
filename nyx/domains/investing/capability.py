"""ValueInvestingCapability — NYX as an autonomous deep-value investor.

Plugs into the generic CapabilityRunner:
- evolves the `analyst` genome against a point-in-time value backtest (real EDGAR
  data when reachable, synthetic otherwise),
- seeds + keeps reading Buffett/Berkshire and SEC filings into long-term memory,
- makes a gated shortlist decision every cycle and gets better as it learns.
"""
from __future__ import annotations

import re

from ...constitution import Constitution
from ...tools.web import WebFetcher
from ..investing import buffett
from ..investing.backtest import INVESTING_DIRECTIVES, ValueBenchmark
from ..investing.data import try_build_universes
from ..investing.gates import check_investing, investing_constitution
from ...capabilities.base import Capability, CycleContext, CycleResult

# A small default watchlist; override via objective or config in real use.
DEFAULT_TICKERS = ["AAPL", "MSFT", "BRK-B", "KO", "JNJ", "PG", "WMT", "XOM",
                   "JPM", "UNH", "HD", "PEP", "CVX", "ABBV", "MRK", "COST"]

# Leading \b only: alternatives are stems ("undervalu", "stock") that must match
# inflected forms ("undervalued", "stocks") — a trailing \b would reject those.
_MATCH = re.compile(
    r"\b(invest|undervalu|deep[\s-]?value|stock|equit|sec\b|edgar|"
    r"buffett|berkshire|annualized return|margin of safety)", re.IGNORECASE)


class ValueInvestingCapability(Capability):
    name = "value-investing"
    description = "Find deep-value public companies; learn from Buffett; evolve against a backtest."

    def __init__(self, tickers: list[str] | None = None):
        self.tickers = tickers or DEFAULT_TICKERS
        self._benchmark: ValueBenchmark | None = None
        self._seeded_letters = False

    def matches(self, objective: str) -> bool:
        return bool(_MATCH.search(objective))

    def allowed_tools(self) -> set[str]:
        # The investor reads filings and the web; it never needs anything else.
        # Built-in filing/web tools + any configured MCP server (e.g.
        # mcp.sec-edgar-mcp) via the prefix wildcard — nothing else.
        return {"web_fetch", "web_crawl", "read_url",
                "edgar_financials", "edgar_filings", "edgar_facts", "mcp.*"}

    def evolve_role(self) -> str:
        return "analyst"

    def directives(self):
        return INVESTING_DIRECTIVES

    def constitution(self, base: Constitution) -> Constitution:
        return investing_constitution(mode=base.mode)

    def seed_memory(self, memory) -> int:
        return buffett.seed_principles(memory)

    def benchmark(self, ctx: CycleContext) -> ValueBenchmark:
        if self._benchmark is None:
            # Prefer a real, point-in-time WALK-FORWARD (several as-of dates);
            # fall back to the synthetic walk-forward if data is unavailable.
            fetcher = WebFetcher(cache_dir=ctx.config.web_cache_dir,
                                 user_agent=ctx.config.user_agent,
                                 allowed_domains=ctx.config.allowed_domains,
                                 rate_limit_seconds=ctx.config.web_rate_limit_seconds)
            universes = try_build_universes(self.tickers, identity=ctx.config.edgar_identity,
                                            fetcher=fetcher)
            self._benchmark = ValueBenchmark(
                universes=universes,   # None → ValueBenchmark uses the synthetic set
                config=ctx.config, provider=ctx.provider,  # LLM-derived factor weights when live
            )
            src = (f"EDGAR live walk-forward ({len(universes)} periods)"
                   if universes else "synthetic walk-forward")
            ctx.ledger.append("value-investing", "universe", rationale=src, decision="INFO")
        return self._benchmark

    def refresh_knowledge(self, ctx: CycleContext) -> dict:
        """Keep reading Berkshire letters + SEC filings into memory (best-effort)."""
        stats = {"letters": 0, "filings": 0, "live": False}
        fetcher = WebFetcher(cache_dir=ctx.config.web_cache_dir, user_agent=ctx.config.user_agent,
                             allowed_domains=ctx.config.allowed_domains,
                             rate_limit_seconds=ctx.config.web_rate_limit_seconds)
        # Berkshire annual letters (recent few; cached so reruns are cheap).
        if not self._seeded_letters:
            res = buffett.fetch_letters(fetcher, ctx.memory, start=2019, end=2024)
            stats["letters"] = res.get("fetched", 0)
            stats["live"] = stats["live"] or res["fetched"] > 0
            self._seeded_letters = True
        # SEC filings: read one company's latest facts via the edgar tool.
        ticker = self.tickers[ctx.cycle_index % len(self.tickers)]
        r = ctx.toolbox.call("edgar_facts", ticker=ticker)
        if r.ok:
            ctx.memory.remember(f"SEC facts read for {ticker}: {r.text(400)}",
                                kind="lesson", tags=["sec", ticker.lower(), "fundamentals"],
                                source="edgar")
            stats["filings"] = 1
            stats["live"] = True

        # Read the FULL latest 10-K end to end (LongDocReader digests it without
        # overflowing context) and store the whole-document synthesis in memory.
        idx_url = ("https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany"
                   f"&ticker={ticker}&type=10-K&dateb=&owner=include&count=1")
        rd = ctx.toolbox.call("read_url", url=idx_url,
                              query="risk factors, debt, leases, litigation, going concern, footnotes")
        if rd.ok and rd.data.strip():
            ctx.memory.remember(f"10-K digest for {ticker}: {rd.text(1500)}",
                                kind="research", tags=["sec", ticker.lower(), "10-k", "filing"],
                                source=idx_url, weight=1.5)
            stats["digested"] = stats.get("digested", 0) + 1
            stats["live"] = True
        return stats

    def plan(self, objective: str, ctx: CycleContext) -> list[str]:
        return [
            "Read fundamentals + footnotes across the universe",
            "Compute margin of safety, ROIC, leverage, owner-earnings",
            "Shortlist the most undervalued, financially sound candidates",
            "Research recent news on the shortlist; discount hype",
            "Rank by risk-adjusted expected return; write Buffett-style memos",
        ]

    def execute(self, task: str, ctx: CycleContext) -> CycleResult:
        bench = self.benchmark(ctx)
        genome = ctx.genomes.get("analyst")
        res = bench.evaluate(genome)
        memo = (f"Shortlist for '{task}': {', '.join(res.picks[:5])}. Selected on margin of "
                f"safety vs intrinsic value, high ROIC, low debt, owner-earnings — per SEC "
                f"filings. Risk-adjusted score {res.score:+.4f}; no guarantees.")
        violations = check_investing(memo)
        ok = not violations
        lessons = [(
            f"Decision for '{task}': picks {res.picks[:5]} score {res.score:+.4f}",
            "pattern", ["investing", "decision"],
        )]
        return CycleResult(
            item=task, ok=ok, summary=memo, score=res.score,
            blocked_at=None if ok else "G_INVESTING", findings=violations, lessons=lessons,
        )
