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
from ..investing.data import try_build_universe
from ..investing.gates import check_investing, investing_constitution
from ...capabilities.base import Capability, CycleContext, CycleResult

# A small default watchlist; override via objective or config in real use.
DEFAULT_TICKERS = ["AAPL", "MSFT", "BRK-B", "KO", "JNJ", "PG", "WMT", "XOM",
                   "JPM", "UNH", "HD", "PEP", "CVX", "ABBV", "MRK", "COST"]

_MATCH = re.compile(
    r"\b(invest|value|undervalu|deep[\s-]?value|stock|equit|compan|sec\b|edgar|"
    r"buffett|berkshire|annualized return|margin of safety)\b", re.IGNORECASE)


class ValueInvestingCapability(Capability):
    name = "value-investing"
    description = "Find deep-value public companies; learn from Buffett; evolve against a backtest."

    def __init__(self, tickers: list[str] | None = None):
        self.tickers = tickers or DEFAULT_TICKERS
        self._benchmark: ValueBenchmark | None = None
        self._seeded_letters = False

    def matches(self, objective: str) -> bool:
        return bool(_MATCH.search(objective))

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
            # Prefer a real, point-in-time universe; fall back to synthetic.
            fetcher = WebFetcher(cache_dir=ctx.config.web_cache_dir,
                                 user_agent=ctx.config.user_agent,
                                 allowed_domains=ctx.config.allowed_domains,
                                 rate_limit_seconds=ctx.config.web_rate_limit_seconds)
            universe = try_build_universe(self.tickers, identity=ctx.config.edgar_identity,
                                          fetcher=fetcher)
            self._benchmark = ValueBenchmark(universes=[universe]) if universe else ValueBenchmark()
            src = "EDGAR(live)" if universe else "synthetic"
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
