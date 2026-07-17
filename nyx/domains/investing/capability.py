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
from ..investing.assess import assess_company, rank_assessments
from ..investing.backtest import (
    INVESTING_DIRECTIVES,
    ValueBenchmark,
    composite_rank,
    weights_for,
)
from ..investing.data import today, try_build_current_universe, try_build_universes
from ..investing.filings import (
    FOOTNOTE_TOPICS,
    MCP_EDGAR,
    bellwether_holdings,
    ingest_company_filings,
    ingest_full_10k,
    readable,
)
from ..investing.gates import check_investing, investing_constitution
from ..investing.news import fetch_news
from ...capabilities.base import Capability, CycleContext, CycleResult

# A small default watchlist; widened at runtime via the SEC screener (edgar_screen)
# and overridable with NYX_INVEST_TICKERS / NYX_INVEST_UNIVERSE_SIZE.
DEFAULT_TICKERS = ["AAPL", "MSFT", "BRK-B", "KO", "JNJ", "PG", "WMT", "XOM",
                   "JPM", "UNH", "HD", "PEP", "CVX", "ABBV", "MRK", "COST"]

_FOOTNOTE_TOPICS = FOOTNOTE_TOPICS   # rotated per cycle during a run
_BELLWETHER_13F = "BRK-B"

# A dedicated run cycle that triggers the whole-market funnel (screen → value →
# deep-read finalists → judge), so a single `nyx run` evolves AND screens live.
SCREEN_TASK = "Screen the whole market today; deep-read finalists' 10-Ks; rank by conviction"

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
        # Letters still to read (recent-first, so a short run gets the most
        # relevant; a long run works through all 45). Lazily filled on first cycle.
        self._letters_todo: list[int] | None = None
        self._seeded_13f = False
        self._discovered = False
        self._digests: dict = {}      # ticker -> DocumentDigest of its full filings

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

    def param_space(self) -> dict:
        """The analyst's continuous genes — what evolution tunes against the
        walk-forward backtest. Four factor weights PLUS the portfolio-construction
        knobs a real value investor sets: risk aversion, concentration, and a
        margin-of-safety floor. This is the search space that breaks the plateau."""
        return {
            "w_mos": (0.0, 3.0, 1.5),          # emphasis on discount to intrinsic value
            "w_roic": (0.0, 3.0, 1.0),         # emphasis on quality / moat
            "w_debt": (0.0, 3.0, 1.0),         # aversion to leverage
            "w_oey": (0.0, 3.0, 1.0),          # emphasis on owner-earnings yield
            "downside_lambda": (0.5, 4.0, 2.0),  # how hard to punish capital loss
            "top_n": (3.0, 15.0, 8.0),         # portfolio concentration
            "mos_floor": (-0.5, 0.4, -0.5),    # minimum margin of safety to hold
        }

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
        # ALL Berkshire letters (1977→present), read end-to-end into memory once
        # (cached, so reruns are cheap). A BATCH of letters is read each cycle —
        # recent-first — so a short run learns the most relevant and a long
        # `--keep-going` run works through all 45, each distilled into durable
        # Buffett doctrine. NYX_BUFFETT_LETTERS_FROM sets the oldest year read.
        if self._letters_todo is None:
            try:
                start = int(os.environ.get("NYX_BUFFETT_LETTERS_FROM", "1977"))
            except ValueError:
                start = 1977
            from datetime import datetime, timezone
            end = datetime.now(tz=timezone.utc).year - 1
            self._letters_todo = list(range(end, start - 1, -1))   # recent-first
        if self._letters_todo:
            try:
                batch_size = max(1, int(os.environ.get("NYX_BUFFETT_LETTERS_PER_CYCLE", "4")))
            except ValueError:
                batch_size = 4
            batch, self._letters_todo = (self._letters_todo[:batch_size],
                                         self._letters_todo[batch_size:])
            res = buffett.fetch_letters(fetcher, ctx.memory, years=batch,
                                        config=ctx.config, provider=ctx.provider)
            stats["letters"] = res.get("fetched", 0)
            stats["principles"] = res.get("principles", 0)
            stats["live"] = stats["live"] or res["fetched"] > 0
            ctx.ledger.append("value-investing", "buffett_letters",
                              rationale=f"read {res.get('fetched', 0)} letters "
                                        f"{batch}, formed {res.get('principles', 0)} "
                                        f"principles, {len(self._letters_todo)} remaining",
                              decision="INFO")

        ticker = self.tickers[ctx.cycle_index % len(self.tickers)]

        if MCP_EDGAR in ctx.toolbox.names():
            # 10-K footnotes for a rotating topic (the real economics hide here).
            topic = _FOOTNOTE_TOPICS[ctx.cycle_index % len(_FOOTNOTE_TOPICS)]
            fn = ctx.toolbox.call(MCP_EDGAR, tool="edgar_notes",
                                  arguments={"identifier": ticker, "topic": topic})
            if fn.ok:
                ctx.memory.remember(
                    f"10-K footnotes ({topic}) for {ticker}: {readable(fn.data, 1400)}",
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
                    f"Insider (Form 4) activity for {ticker}: {readable(ins.data, 900)}",
                    kind="research", tags=["sec", ticker.lower(), "insider", "form-4"],
                    source="edgartools-mcp", weight=1.4, trusted=False)
                stats["insider"] = 1
                stats["live"] = True
            # Recent material events (8-K).
            ev = ctx.toolbox.call(MCP_EDGAR, tool="edgar_filing",
                                  arguments={"identifier": ticker, "form": "8-K"})
            if ev.ok:
                ctx.memory.remember(
                    f"Recent 8-K events for {ticker}: {readable(ev.data, 900)}",
                    kind="research", tags=["sec", ticker.lower(), "8-k", "events"],
                    source="edgartools-mcp", weight=1.3, trusted=False)
                stats["events_8k"] = 1
                stats["live"] = True
            # A bellwether investor's actual 13F positions (read once). The MCP tool
            # reports only a holdings *count*, so the real infotable is read direct.
            if not self._seeded_13f:
                self._seeded_13f = True
                owners = bellwether_holdings(identity=ctx.config.edgar_identity)
                if owners:
                    top = sorted(owners, key=lambda t: t)[:40]
                    ctx.memory.remember(
                        f"13F holdings of {_BELLWETHER_13F} ({len(owners)} positions): "
                        f"{', '.join(top)}",
                        kind="research", tags=["sec", "13f", "holdings", "bellwether"],
                        source="edgartools-13f", weight=1.6, trusted=False)
                    stats["holdings_13f"] = len(owners)
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

    def _deep_read_all(self, ctx: CycleContext, tickers: list[str]) -> int:
        """Read each finalist's filings end-to-end into memory — nothing truncated.

        For every ticker: the FULL raw 10-K (Business + Risk Factors + MD&A + notes,
        hundreds of KB) is run through NYX's long-document engine — chunked, folded
        into a bounded synthesis, and embedded so any passage stays retrievable —
        plus structured footnotes/8-K/Form 4 via the MCP server. Distillation is the
        free deterministic fold by default; ``NYX_DEEP_READ_LLM=1`` uses the model
        (~1 call/chunk). Idempotent: a company already read is skipped."""
        use_llm = os.environ.get("NYX_DEEP_READ_LLM", "0") == "1"
        cfg, provider = (ctx.config, ctx.provider) if use_llm else (None, None)
        have_mcp = MCP_EDGAR in ctx.toolbox.names()
        read = 0
        for ticker in tickers:
            if ticker in self._digests:
                continue
            # The entire 10-K, read whole via the long-document reader.
            digest = ingest_full_10k(ctx.memory, ticker, identity=ctx.config.edgar_identity,
                                     config=cfg, provider=provider)
            # Structured footnotes / 8-K / insider on top (recent, machine-parsed).
            if have_mcp:
                mcp_digest = ingest_company_filings(ctx.memory, ctx.toolbox, ticker,
                                                    config=cfg, provider=provider)
                digest = digest or mcp_digest
            if digest is not None:
                self._digests[ticker] = digest
                read += 1
        ctx.ledger.append("value-investing", "deep_read",
                          rationale=f"read full 10-K + filings for {read}/{len(tickers)} finalists",
                          decision="INFO")
        return read

    def _market_candidates(self, ctx: CycleContext, fetcher) -> list[str]:
        """Funnel stage 1: quality-screen the WHOLE market (price-free, ~7 bulk SEC
        calls) down to the strongest candidates. Falls back to the screener/watchlist
        if the bulk endpoints are unreachable."""
        from ..investing.market import market_universe_tickers
        try:
            wide = max(20, int(os.environ.get("NYX_SCREEN_WIDE", "120")))
        except ValueError:
            wide = 120
        try:
            tickers = market_universe_tickers(fetcher, top_n=wide)
        except Exception:  # noqa: BLE001 — degrade to the narrow screener
            tickers = []
        if tickers:
            ctx.ledger.append("value-investing", "market_screen",
                              rationale=f"quality-screened whole market → {len(tickers)} candidates",
                              decision="INFO")
            return tickers
        self._discover_universe(ctx)
        return self.tickers

    def _evidence_for(self, ticker: str, ctx: CycleContext) -> str:
        """Pull the filing passages that actually bear on the decision, by embedding
        retrieval over the company's deep-read digest (detail without truncation)."""
        query = ("debt covenants leverage litigation contingencies leases impairment "
                 "insider selling revenue recognition going concern moat")
        digest = self._digests.get(ticker)
        if digest is not None:
            return "\n---\n".join(digest.retrieve(query, k=3))[:6000]
        hits = ctx.memory.recall(f"{ticker} SEC filings footnotes", k=2)
        return "\n---\n".join(h.text for h in hits)[:6000] or "(no filing evidence read)"

    def screen_today(self, ctx: CycleContext, *, top_n: int = 8) -> list:
        """Predict: apply the EVOLVED doctrine to today's fundamentals, as a funnel.

        Training happens on the historical walk-forward (which needs realized returns
        to score); prediction happens here, as of today, where no forward return can
        exist yet. Same factors, same genome — only the as-of date moves.

        Funnel: (1) quality-screen the WHOLE market price-free (~7 bulk SEC calls);
        (2) fetch real prices for the survivors and rank by the evolved composite
        (now including margin of safety); (3) read each finalist's ENTIRE 10-K plus
        footnotes/8-K/insider into memory; (4) have the analyst judge each finalist
        against the filings, Buffett doctrine, and 13F ownership.
        """
        if ctx.config.mock_mode or not ctx.config.edgar_identity:
            ctx.ledger.append("value-investing", "screen_today",
                              rationale="needs a live brain + EDGAR_IDENTITY — skipped",
                              decision="INFO")
            return []
        fetcher = WebFetcher(cache_dir=ctx.config.web_cache_dir,
                             user_agent=ctx.config.edgar_identity or ctx.config.user_agent,
                             allowed_domains=ctx.config.allowed_domains,
                             rate_limit_seconds=ctx.config.web_rate_limit_seconds)
        as_of = today()

        # Stage 1 — whole-market quality screen (price-free).
        candidates = self._market_candidates(ctx, fetcher)

        # Stage 2 — value the survivors with real prices, rank by the evolved genome.
        universe = try_build_current_universe(candidates, as_of=as_of,
                                              identity=ctx.config.edgar_identity, fetcher=fetcher)
        if universe is None:
            ctx.ledger.append("value-investing", "screen_today",
                              rationale="live data unavailable — no current screen",
                              decision="BLOCK")
            return []
        genome = ctx.genomes.get("analyst")
        # The SAME evolved doctrine (params → LLM → keywords) that won the backtest
        # ranks today's names, so training transfers to the live shortlist.
        weights = weights_for(genome, ctx.config, ctx.provider, metrics=ctx.metrics)
        ranked = composite_rank(universe, weights)

        # Stage 3 — deep-read only the finalists (full 10-K + filings), then judge them.
        try:
            deep_n = max(1, int(os.environ.get("NYX_SCREEN_DEEP", "15")))
        except ValueError:
            deep_n = 15
        finalists = ranked[:deep_n]
        self._deep_read_all(ctx, [c.ticker for _, c in finalists])
        owners = bellwether_holdings(identity=ctx.config.edgar_identity)
        # Doctrine, incl. cross-domain principles (research rigor, etc.) federated
        # from sibling capability stores — durable wisdom, not noisy research.
        doctrine_q = ("Buffett doctrine margin of safety moat durable competitive "
                      "advantage owner earnings ROIC leverage compounding")
        principles_pool = list(ctx.memory.recall(doctrine_q, k=8))
        principles_pool += [ln for ln in ctx.memory.recall_doctrine(doctrine_q, k=4)
                            if ln.id not in {p.id for p in principles_pool}]
        principles = "\n".join(f"- {lesson.text}" for lesson in principles_pool)
        doctrine = genome.system_prompt if genome else ""

        # Stage 4 — judgment. Only the deep-read finalists get the (paid) LLM read;
        # the rest keep their factor rank (offline assessment is neutral).
        assessments = []
        for rank_i, (factor_score, co) in enumerate(ranked):
            metrics = (f"market cap ${co.price / 1e9:,.1f}B; conservative intrinsic value "
                       f"${co.intrinsic_value / 1e9:,.1f}B; margin of safety "
                       f"{co.margin_of_safety:+.1%}; ROIC {co.roic:+.1%}; debt/equity "
                       f"{co.debt_to_equity:.2f}; owner-earnings yield "
                       f"{co.owner_earnings_yield:+.1%}")
            judged = rank_i < deep_n and ctx.metrics.calls < ctx.config.max_calls
            assessments.append(assess_company(
                ctx.config if judged else None, ctx.provider if judged else None,
                ticker=co.ticker, factor_score=factor_score, metrics=metrics,
                principles=principles, evidence=self._evidence_for(co.ticker, ctx),
                held_by=owners.get(co.ticker, []), doctrine=doctrine,
                run_metrics=ctx.metrics))

        final = rank_assessments(assessments)
        ctx.ledger.append("value-investing", "screen_today",
                          rationale=f"as_of={as_of}: {len(candidates)} screened → "
                                    f"{len(universe.companies)} valued → {len(finalists)} deep-read; "
                                    f"top: {', '.join(a.ticker for a in final[:5])}",
                          decision="PASS")
        for a in final[:top_n]:
            ctx.memory.remember(
                f"CURRENT SCREEN {as_of} — {a.ticker}: conviction {a.llm_score:.1f}/10, "
                f"factor {a.factor_score:+.2f}, final {a.final_score:.3f}. {a.rationale}",
                kind="research", tags=["investing", "screen", a.ticker.lower(), "current"],
                source="screen_today", weight=1.5, trusted=False)
        return final[:top_n]

    def plan(self, objective: str, ctx: CycleContext) -> list[str]:
        tasks = [
            "Read fundamentals + footnotes across the universe",
            "Compute margin of safety, ROIC, leverage, owner-earnings",
            "Shortlist the most undervalued, financially sound candidates",
            "Research recent news on the shortlist; discount hype",
            "Rank by risk-adjusted expected return; write Buffett-style memos",
        ]
        # The whole-market funnel is a live-data cycle: include it only when a real
        # brain + SEC identity are present (keeps offline/mock runs deterministic).
        if not ctx.config.mock_mode and ctx.config.edgar_identity:
            tasks.append(SCREEN_TASK)
        return tasks

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

    def _execute_screen(self, task: str, ctx: CycleContext) -> CycleResult:
        """A run cycle that runs the whole-market funnel: screen → value → deep-read
        finalists' full 10-Ks → judge. Its output (picks + rationales) is reflected
        into memory, so the same `nyx run` both evolves the analyst and produces a
        current, filings-grounded shortlist."""
        picks = self.screen_today(ctx, top_n=8)
        if not picks:
            return CycleResult(item=task, ok=True, score=None,
                               summary="Current screen unavailable (live SEC/price data).",
                               lessons=[])
        lines = [f"{a.ticker}: conviction {a.llm_score:.1f}/10, final {a.final_score:.3f}"
                 f"{' [13F-owned]' if a.held_by else ''} — {a.rationale[:80]}" for a in picks]
        memo = ("CURRENT SCREEN (today) — read full 10-Ks, footnotes, 8-K, insider, 13F; "
                "ranked by conviction + value factors; no guarantees:\n" + "\n".join(lines))
        violations = check_investing(memo)
        lessons = [(f"CURRENT SCREEN — top conviction picks today: "
                    f"{', '.join(a.ticker for a in picks[:5])}.",
                    "research", ["investing", "screen", "current"])]
        return CycleResult(
            item=task, ok=not violations, summary=memo, score=round(picks[0].final_score, 4),
            blocked_at=None if not violations else "G_INVESTING",
            findings=violations, lessons=lessons,
        )

    def execute(self, task: str, ctx: CycleContext) -> CycleResult:
        if task == SCREEN_TASK:
            return self._execute_screen(task, ctx)
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
