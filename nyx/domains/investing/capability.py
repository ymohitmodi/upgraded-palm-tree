"""ValueInvestingCapability — NYX as an autonomous deep-value investor.

Plugs into the generic CapabilityRunner:
- evolves the `analyst` genome against a point-in-time value backtest (real EDGAR
  data when reachable, synthetic otherwise),
- seeds + keeps reading Buffett/Berkshire and SEC filings into long-term memory,
- makes a gated shortlist decision every cycle and gets better as it learns.
"""
from __future__ import annotations

import json
import os
import re

from ...constitution import Constitution
from ...tools.web import WebFetcher
from ..investing import buffett
from ..investing.backtest import INVESTING_DIRECTIVES, ValueBenchmark
from ..investing.data import try_build_universes
from ..investing.gates import check_investing, investing_constitution
from ..investing.news import fetch_news
from ...capabilities.base import Capability, CycleContext, CycleResult

MCP_EDGAR = "mcp.edgartools"

# A small default watchlist; widened at runtime via the SEC screener (edgar_screen)
# and overridable with NYX_INVEST_TICKERS / NYX_INVEST_UNIVERSE_SIZE.
DEFAULT_TICKERS = ["AAPL", "MSFT", "BRK-B", "KO", "JNJ", "PG", "WMT", "XOM",
                   "JPM", "UNH", "HD", "PEP", "CVX", "ABBV", "MRK", "COST"]

# Footnote topics rotated through as the analyst re-reads filings cycle by cycle.
_FOOTNOTE_TOPICS = ["debt", "leases", "litigation", "income taxes",
                    "commitments and contingencies", "revenue recognition"]
# A great investor whose 13F holdings are worth reading as a signal.
_BELLWETHER_13F = "BRK-B"

# Leading \b only: alternatives are stems ("undervalu", "stock") that must match
# inflected forms ("undervalued", "stocks") — a trailing \b would reject those.
_MATCH = re.compile(
    r"\b(invest|undervalu|deep[\s-]?value|stock|equit|sec\b|edgar|"
    r"buffett|berkshire|annualized return|margin of safety)", re.IGNORECASE)


class ValueInvestingCapability(Capability):
    name = "value-investing"
    description = "Find deep-value public companies; learn from Buffett; evolve against a backtest."

    def __init__(self, tickers: list[str] | None = None):
        env_tickers = [t.strip().upper() for t in os.environ.get("NYX_INVEST_TICKERS", "").split(",")
                       if t.strip()]
        self.tickers = tickers or env_tickers or DEFAULT_TICKERS
        self._benchmark: ValueBenchmark | None = None
        self._seeded_letters = False
        self._seeded_13f = False
        self._discovered = False

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

    def eval(self, config, provider):
        from ...capabilities.base import EvalResult
        from ...evolution.archive import Archive
        from ..investing.backtest import ValueBenchmark, heldout_universes

        best = Archive(config.evolution_archive).best_for("analyst")
        genome = best.to_genome() if best else None
        res = ValueBenchmark(universes=heldout_universes(),
                             config=config, provider=provider).evaluate(genome)
        return EvalResult(score=res.score,
                          detail=f"held-out value walk-forward, {'evolved' if best else 'seed'} analyst")

    def directives(self):
        return INVESTING_DIRECTIVES

    def constitution(self, base: Constitution) -> Constitution:
        return investing_constitution(mode=base.mode)

    def seed_memory(self, memory) -> int:
        return buffett.seed_principles(memory)

    def _discover_universe(self, ctx: CycleContext) -> None:
        """Widen the watchlist by screening SEC (edgar_screen) for real candidates,
        so the analyst discovers names across the market rather than ranking a fixed
        handful. Bounded by NYX_INVEST_UNIVERSE_SIZE to keep the build tractable."""
        if self._discovered or MCP_EDGAR not in ctx.toolbox.names():
            return
        self._discovered = True
        try:
            size = max(len(self.tickers), int(os.environ.get("NYX_INVEST_UNIVERSE_SIZE", "24")))
        except ValueError:
            size = 24
        found = list(self.tickers)
        for exchange in ("NYSE", "Nasdaq"):
            if len(found) >= size:
                break
            r = ctx.toolbox.call(MCP_EDGAR, tool="edgar_screen",
                                 arguments={"exchange": exchange, "limit": 60})
            if not r.ok:
                continue
            try:
                companies = json.loads(r.data).get("data", {}).get("companies", [])
            except (ValueError, TypeError, AttributeError):
                companies = []
            for co in companies:
                t = (co.get("ticker") or "").strip().upper()
                if t and t not in found:
                    found.append(t)
                    if len(found) >= size:
                        break
        added = len(found) - len(self.tickers)
        self.tickers = found[:size]
        ctx.ledger.append("value-investing", "screen",
                          rationale=f"widened universe to {len(self.tickers)} (+{added} via SEC screener)",
                          decision="INFO")

    def benchmark(self, ctx: CycleContext) -> ValueBenchmark:
        if self._benchmark is None:
            self._discover_universe(ctx)
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
            src = (f"EDGAR live walk-forward ({len(universes)} periods, "
                   f"{len(self.tickers)} names)" if universes else "synthetic walk-forward")
            ctx.ledger.append("value-investing", "universe", rationale=src, decision="INFO")
        return self._benchmark

    def refresh_knowledge(self, ctx: CycleContext) -> dict:
        """Keep reading real SEC primary sources into memory (best-effort).

        Per cycle, for the rotating focus ticker, pull via the edgartools MCP
        server: 10-K footnotes (rotating topic), insider trades (Form 4), and
        recent 8-K events; once, a bellwether 13F. Falls back to the built-in
        ``edgar_facts`` tool when the MCP server isn't registered."""
        stats: dict = {"letters": 0, "footnotes": 0, "insider": 0, "events_8k": 0,
                       "holdings_13f": 0, "live": False}
        fetcher = WebFetcher(cache_dir=ctx.config.web_cache_dir, user_agent=ctx.config.user_agent,
                             allowed_domains=ctx.config.allowed_domains,
                             rate_limit_seconds=ctx.config.web_rate_limit_seconds)
        # Berkshire annual letters (recent few; cached so reruns are cheap).
        if not self._seeded_letters:
            res = buffett.fetch_letters(fetcher, ctx.memory, start=2019, end=2024)
            stats["letters"] = res.get("fetched", 0)
            stats["live"] = stats["live"] or res["fetched"] > 0
            self._seeded_letters = True

        ticker = self.tickers[ctx.cycle_index % len(self.tickers)]

        if MCP_EDGAR in ctx.toolbox.names():
            # 10-K footnotes for a rotating topic (the real economics hide here).
            topic = _FOOTNOTE_TOPICS[ctx.cycle_index % len(_FOOTNOTE_TOPICS)]
            fn = ctx.toolbox.call(MCP_EDGAR, tool="edgar_notes",
                                  arguments={"identifier": ticker, "topic": topic})
            if fn.ok:
                ctx.memory.remember(
                    f"10-K footnotes ({topic}) for {ticker}: {fn.text(1400)}",
                    kind="research", tags=["sec", ticker.lower(), "footnotes", "10-k"],
                    source="edgartools-mcp", weight=1.6, trusted=False)
                stats["footnotes"] = 1
                stats["live"] = True
            # Insider transactions (Form 4) — management conviction signal.
            ins = ctx.toolbox.call(MCP_EDGAR, tool="edgar_ownership",
                                   arguments={"identifier": ticker,
                                              "analysis_type": "insiders", "limit": 10})
            if ins.ok:
                ctx.memory.remember(
                    f"Insider (Form 4) activity for {ticker}: {ins.text(900)}",
                    kind="research", tags=["sec", ticker.lower(), "insider", "form-4"],
                    source="edgartools-mcp", weight=1.4, trusted=False)
                stats["insider"] = 1
                stats["live"] = True
            # Recent material events (8-K).
            ev = ctx.toolbox.call(MCP_EDGAR, tool="edgar_filing",
                                  arguments={"identifier": ticker, "form": "8-K"})
            if ev.ok:
                ctx.memory.remember(
                    f"Recent 8-K events for {ticker}: {ev.text(900)}",
                    kind="research", tags=["sec", ticker.lower(), "8-k", "events"],
                    source="edgartools-mcp", weight=1.3, trusted=False)
                stats["events_8k"] = 1
                stats["live"] = True
            # A bellwether investor's 13F holdings (read once) — what great
            # capital allocators actually own.
            if not self._seeded_13f:
                self._seeded_13f = True
                f13 = ctx.toolbox.call(MCP_EDGAR, tool="edgar_ownership",
                                       arguments={"identifier": _BELLWETHER_13F,
                                                  "analysis_type": "fund_portfolio", "limit": 25})
                if f13.ok:
                    ctx.memory.remember(
                        f"13F holdings of {_BELLWETHER_13F}: {f13.text(1400)}",
                        kind="research", tags=["sec", "13f", "holdings", "bellwether"],
                        source="edgartools-mcp", weight=1.6, trusted=False)
                    stats["holdings_13f"] = 1
                    stats["live"] = True
        else:
            # Fallback: standardized XBRL facts via the built-in tool.
            r = ctx.toolbox.call("edgar_facts", ticker=ticker)
            if r.ok:
                ctx.memory.remember(f"SEC facts read for {ticker}: {r.text(600)}",
                                    kind="lesson", tags=["sec", ticker.lower(), "fundamentals"],
                                    source="edgar", trusted=False)
                stats["footnotes"] = 1
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

    def _research_news(self, ctx: CycleContext, picks: list[str]) -> int:
        """Read recent news on the shortlist and store it (untrusted) so the
        analyst can discount hype. Best-effort; never sinks a cycle."""
        if ctx.config.mock_mode:   # offline/tests: don't reach the network
            return 0
        allow = ctx.config.allowed_domains
        if allow and "news.google.com" not in allow:   # respect egress policy
            return 0
        fetcher = WebFetcher(cache_dir=ctx.config.web_cache_dir, user_agent=ctx.config.user_agent,
                             allowed_domains=ctx.config.allowed_domains,
                             rate_limit_seconds=ctx.config.web_rate_limit_seconds)
        researched = 0
        for ticker in picks[:3]:
            headlines = fetch_news(fetcher, f"{ticker} stock", limit=6)
            if not headlines:
                continue
            digest = " | ".join(h.title for h in headlines)
            ctx.memory.remember(
                f"Recent news on {ticker}: {digest[:1000]}",
                kind="research", tags=["news", ticker.lower(), "sentiment"],
                source="news.google.com", weight=1.2, trusted=False)  # discount hype
            researched += 1
        if researched:
            ctx.ledger.append("value-investing", "research_news",
                              rationale=f"read news on {researched} names", decision="INFO")
        return researched

    def execute(self, task: str, ctx: CycleContext) -> CycleResult:
        bench = self.benchmark(ctx)
        genome = ctx.genomes.get("analyst")
        res = bench.evaluate(genome)
        # Research recent news on the shortlist (discount hype vs. the filings).
        researched = self._research_news(ctx, res.picks)
        memo = (f"Shortlist for '{task}': {', '.join(res.picks[:5])}. Selected on margin of "
                f"safety vs intrinsic value, high ROIC, low debt, owner-earnings — per SEC "
                f"filings; recent news reviewed on {researched} names. Risk-adjusted score "
                f"{res.score:+.4f}; no guarantees.")
        violations = check_investing(memo)
        ok = not violations
        # Outer feedback loop: record the REALIZED risk-adjusted return of the
        # picks (the backtest is the ground-truth outcome) as a trusted track
        # record, so performance — not opinion — accumulates and is recalled.
        lessons = [(
            f"TRACK RECORD — '{task[:50]}': picks {res.picks[:5]} realized "
            f"risk-adjusted return {res.score:+.4f} (portfolio {res.portfolio_return:+.2%}, "
            f"downside {res.downside:+.2%}).",
            "track-record", ["investing", "track-record", "realized"],
        )]
        return CycleResult(
            item=task, ok=ok, summary=memo, score=res.score,
            blocked_at=None if ok else "G_INVESTING", findings=violations, lessons=lessons,
        )
