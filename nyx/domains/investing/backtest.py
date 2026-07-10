"""Point-in-time value backtest — the fitness signal for evolving the analyst.

This is the keystone that makes "keep evolving to get better at value investing"
*measurable*. It plugs into the existing Darwin-Gödel engine as a benchmark:

    from nyx.domains.investing.backtest import ValueBenchmark, INVESTING_DIRECTIVES
    engine = EvolutionEngine(role="analyst", benchmark=ValueBenchmark(),
                             directive_pool=INVESTING_DIRECTIVES)
    engine.evolve(generations=20)

How it avoids cheating (the usual backtest traps):

- **No look-ahead**: the analyst genome only influences *which factors it weighs*
  (margin of safety, ROIC, leverage, owner-earnings) — computed from data known
  *as of T*. Forward returns are hidden and used **only** to score the portfolio
  it picks.
- **Don't-lose-money is priced in**: the score is forward return with a heavy
  penalty on downside (picks that lost money), matching the constitution's
  capital-preservation gate.
- **The doctrine has to actually work**: in the data, sound value factors
  genuinely predict forward returns, so a genome that encodes the Buffett
  doctrine backtests better — and evolution discovers that on its own.

Offline it runs on a deterministic synthetic universe (so tests/CI are stable).
Swap ``default_universe()`` for real EDGAR fundamentals + realized forward
prices and the exact same mechanics become a real walk-forward backtest.
"""
from __future__ import annotations

import random
import re
from dataclasses import dataclass, field

from ...agents.base import Agent, Genome

# Investing-flavored charter directives the engine can graft during evolution.
# A broad pool (with varied factor emphasis and intensity) enlarges the reachable
# doctrine space, so evolution keeps finding admissible gains instead of plateauing
# after a couple of grafts. Each maps onto the four factors by its keywords.
INVESTING_DIRECTIVES = [
    "Require a margin of safety of at least 30% versus conservative intrinsic value.",
    "Demand a deep margin of safety; buy far below intrinsic value or not at all.",
    "Strongly prefer high return on invested capital (ROIC) and durable moats.",
    "Insist on a durable competitive moat with high, stable ROIC and pricing power.",
    "Penalize leverage: avoid high debt-to-equity; read the footnotes for hidden debt.",
    "Treat balance-sheet debt and off-balance-sheet leases as disqualifying risk.",
    "Value owner-earnings yield (distributable cash), not accounting EPS.",
    "Prize consistent, growing owner-earnings and free cash flow across cycles.",
    "Never guarantee returns; protect against permanent loss of capital first.",
    "Avoid value traps: cheapness without quality or a catalyst is not a buy.",
    "Require insider alignment and honest, owner-oriented capital allocation.",
    "Stay within the circle of competence; favor simple, predictable businesses.",
    "Prefer asset-light compounders that reinvest at high rates of return.",
    "Discount hype; weight the filings and footnotes over the narrative.",
]


@dataclass
class Company:
    ticker: str
    price: float
    intrinsic_value: float          # conservative estimate, as of T
    roic: float                     # 0..1
    debt_to_equity: float           # 0..3
    owner_earnings_yield: float     # 0..0.2
    forward_return: float = 0.0     # HIDDEN: realized 1y return (scoring only)

    @property
    def margin_of_safety(self) -> float:
        if self.intrinsic_value <= 0:
            return -1.0
        return (self.intrinsic_value - self.price) / self.intrinsic_value


@dataclass
class Universe:
    as_of: str
    companies: list[Company] = field(default_factory=list)


def default_universe(n: int = 60, seed: int = 7) -> Universe:
    """A deterministic synthetic universe where sound value factors *do* predict
    forward returns (plus noise) — so the doctrine is learnable, not given. The
    factor coefficients are skewed (margin of safety and owner-earnings matter
    most), so equal-weighting is good but *not* optimal — leaving room to evolve."""
    rng = random.Random(seed)
    companies = []
    for i in range(n):
        roic = rng.uniform(0.02, 0.30)
        dte = rng.uniform(0.0, 2.5)
        oey = rng.uniform(0.0, 0.15)
        intrinsic = rng.uniform(50, 150)
        mos = rng.uniform(-0.4, 0.6)              # some cheap, some expensive
        price = max(1.0, intrinsic * (1 - mos))
        # Ground truth: cheap + cash-generative matter most; quality less; debt hurts.
        fwd = (0.02 + 0.60 * mos + 0.25 * (roic - 0.15) - 0.10 * dte
               + 0.70 * (oey - 0.05) + rng.uniform(-0.10, 0.10))
        companies.append(Company(
            ticker=f"SYN{i:02d}", price=round(price, 2), intrinsic_value=round(intrinsic, 2),
            roic=round(roic, 4), debt_to_equity=round(dte, 3),
            owner_earnings_yield=round(oey, 4), forward_return=round(fwd, 4),
        ))
    return Universe(as_of=f"T{seed}", companies=companies)


def default_universes(seeds: tuple[int, ...] = (7, 11, 13)) -> list[Universe]:
    """Several independent universes — averaging over them is a mini walk-forward
    that punishes overfitting to any single period's noise."""
    return [default_universe(seed=s) for s in seeds]


def heldout_universes(seeds: tuple[int, ...] = (101, 103, 107)) -> list[Universe]:
    """Held-out universes (seeds disjoint from the training set) for standing
    evaluation — the eval score is not contaminated by training data."""
    return [default_universe(seed=s) for s in seeds]


def _z(values: list[float]) -> list[float]:
    n = len(values)
    mean = sum(values) / n
    var = sum((v - mean) ** 2 for v in values) / n
    sd = var ** 0.5 or 1.0
    return [(v - mean) / sd for v in values]


_FACTORS = ("mos", "roic", "debt", "oey")
_FACTOR_DESC = {
    "mos": "margin of safety / discount to intrinsic value",
    "roic": "return on invested capital, moat, business quality",
    "debt": "penalizing leverage / balance-sheet risk",
    "oey": "owner-earnings / distributable-cash yield",
}


def genome_factor_weights(genome: Genome | None) -> dict:
    """Deterministic OFFLINE fallback: read the charter's factor emphasis.

    Counts are capped so evolution cannot reward-hack by keyword stuffing. When a
    live brain is available, ``llm_factor_weights`` supersedes this — the model,
    not substring rules, decides how the analyst weighs factors.
    """
    base = {f: 0.0 for f in _FACTORS}
    text = (genome.system_prompt.lower() if genome else "")

    def hits(*terms: str) -> float:
        # Cap at 3 (was 2) so a richer directive pool yields finer weight gradation
        # — more distinguishable genomes for evolution to select among.
        return min(sum(text.count(t) for t in terms), 3)

    base["mos"] += 1.0 * hits("margin of safety", "intrinsic", "cheap", "undervalu", "below")
    base["roic"] += 1.0 * hits("roic", "moat", "quality", "compounder", "reinvest")
    base["debt"] += 1.0 * hits("debt", "leverage", "footnote", "lease", "balance-sheet")
    base["oey"] += 1.0 * hits("owner-earnings", "owner earnings", "distributable cash",
                              "free cash flow", "cash flow")
    return base


def llm_factor_weights(genome: Genome | None, config, provider, *, metrics=None) -> dict:
    """Ask the model how strongly the analyst's charter emphasizes each factor.

    No substring rules: the LLM reads the doctrine and rates each factor 0–3.
    Falls back to the deterministic reader on mock mode or any parse failure.
    Pass ``metrics`` to account the call against the run budget."""
    if genome is None or config is None or provider is None or config.mock_mode:
        return genome_factor_weights(genome)
    from ...providers.base import ChatMessage

    factors = "\n".join(f"- {k}: {v}" for k, v in _FACTOR_DESC.items())
    prompt = (
        "You are calibrating a value-investing screen. Given the analyst's charter, "
        "rate how strongly it emphasizes each factor from 0 (ignores) to 3 (central).\n\n"
        f"CHARTER:\n{genome.system_prompt}\n\nFACTORS:\n{factors}\n\n"
        "Reply with ONLY four numbers in order mos,roic,debt,oey — e.g. `2,1,1,3`."
    )
    try:
        # Enough headroom for a reasoning model to finish thinking and then answer.
        completion = provider.chat(config.model("fast"),
                                   [ChatMessage(role="user", content=prompt)],
                                   temperature=0.0, max_tokens=512)
        if metrics is not None:
            metrics.record_call(completion.prompt_tokens, completion.completion_tokens)
        out = completion.text
        nums = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", out)][:4]
        if len(nums) == 4:
            return {f: min(max(n, 0.0), 3.0) for f, n in zip(_FACTORS, nums)}
    except Exception:  # noqa: BLE001 — never let scoring crash a run
        pass
    return genome_factor_weights(genome)


def composite_rank(universe: Universe, w: dict) -> list[tuple[float, Company]]:
    """Rank a universe by the analyst's weighted composite of the four value
    factors (each cross-sectionally z-scored, so scale never matters).

    Shared by the historical backtest scorer and the as-of-today live screen —
    the *same* doctrine ranks past and present, which is what makes the evolved
    genome transferable from training to prediction.
    """
    cos = universe.companies
    z_mos = _z([c.margin_of_safety for c in cos])
    z_roic = _z([c.roic for c in cos])
    z_debt = _z([c.debt_to_equity for c in cos])
    z_oey = _z([c.owner_earnings_yield for c in cos])
    scored = [
        (w["mos"] * z_mos[i] + w["roic"] * z_roic[i]
         - w["debt"] * z_debt[i] + w["oey"] * z_oey[i], c)
        for i, c in enumerate(cos)
    ]
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored


@dataclass
class BacktestResult:
    picks: list[str]
    portfolio_return: float
    downside: float
    score: float


class ValueBenchmark:
    """Callable benchmark: ``ValueBenchmark()(agent) -> float`` (risk-adj return).

    Evaluates across several universes and averages — a mini walk-forward so the
    fitness signal rewards a *robust* doctrine, not a fit to one period's noise.
    """

    def __init__(self, universes: list[Universe] | None = None, top_n: int = 8,
                 downside_lambda: float = 2.0, config=None, provider=None):
        self.universes = universes or default_universes()
        self.top_n = top_n
        self.downside_lambda = downside_lambda
        # When present + live, the LLM (not substring rules) sets factor weights.
        self.config = config
        self.provider = provider

    def evaluate(self, genome: Genome | None) -> BacktestResult:
        # Compute the analyst's factor emphasis ONCE per evaluation (LLM when
        # live, deterministic fallback otherwise) — genome-dependent, universe-
        # independent, so it's reused across the walk-forward universes.
        weights = llm_factor_weights(genome, self.config, self.provider)
        results = [self._evaluate_one(u, weights) for u in self.universes]
        avg_score = round(sum(r.score for r in results) / len(results), 4)
        avg_return = round(sum(r.portfolio_return for r in results) / len(results), 4)
        avg_down = round(sum(r.downside for r in results) / len(results), 4)
        # Report picks from the first universe for display; score is the average.
        return BacktestResult(picks=results[0].picks, portfolio_return=avg_return,
                              downside=avg_down, score=avg_score)

    def _evaluate_one(self, universe: Universe, w: dict) -> BacktestResult:
        scored = composite_rank(universe, w)
        picks = [c for _, c in scored[: self.top_n]]

        port = sum(c.forward_return for c in picks) / len(picks)
        downside = sum(min(0.0, c.forward_return) for c in picks) / len(picks)
        # Risk-adjusted: reward return, punish capital loss ("don't lose money").
        score = round(port + self.downside_lambda * downside, 4)
        return BacktestResult(
            picks=[c.ticker for c in picks],
            portfolio_return=round(port, 4), downside=round(downside, 4), score=score,
        )

    def __call__(self, agent: Agent) -> float:
        return self.evaluate(agent.genome).score
