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
from dataclasses import dataclass, field

from ...agents.base import Agent, Genome

# Investing-flavored charter directives the engine can graft during evolution.
INVESTING_DIRECTIVES = [
    "Require a margin of safety of at least 30% versus conservative intrinsic value.",
    "Strongly prefer high return on invested capital (ROIC) and durable moats.",
    "Penalize leverage: avoid high debt-to-equity; read the footnotes for hidden debt.",
    "Value owner-earnings yield (distributable cash), not accounting EPS.",
    "Never guarantee returns; protect against permanent loss of capital first.",
    "Stay within the circle of competence; favor simple, predictable businesses.",
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


def _z(values: list[float]) -> list[float]:
    n = len(values)
    mean = sum(values) / n
    var = sum((v - mean) ** 2 for v in values) / n
    sd = var ** 0.5 or 1.0
    return [(v - mean) / sd for v in values]


def genome_factor_weights(genome: Genome | None) -> dict:
    """Derive factor weights from what the analyst's charter emphasizes.

    This is the *only* channel by which the evolved genome affects picks — so a
    genome that encodes the value doctrine tilts toward the factors that matter.
    """
    # A genome with no doctrine applies no value factors (picks ~arbitrarily);
    # only the principles it encodes turn factors on — so doctrine has to be
    # *learned* (or seeded), and emphasis differs as evolution accumulates it.
    base = {"mos": 0.0, "roic": 0.0, "debt": 0.0, "oey": 0.0}
    text = (genome.system_prompt.lower() if genome else "")
    # Counts are CAPPED so evolution cannot reward-hack by stuffing the same
    # keyword-bearing directive repeatedly — emphasis saturates at 2 mentions.
    def hits(*terms: str) -> float:
        return min(sum(text.count(t) for t in terms), 2)

    base["mos"] += 1.5 * hits("margin of safety", "intrinsic")
    base["roic"] += 1.5 * hits("roic", "moat", "quality")
    base["debt"] += 1.5 * hits("debt", "leverage", "footnote")
    base["oey"] += 1.5 * hits("owner-earnings", "owner earnings", "distributable cash")
    return base


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
                 downside_lambda: float = 2.0):
        self.universes = universes or default_universes()
        self.top_n = top_n
        self.downside_lambda = downside_lambda

    def evaluate(self, genome: Genome | None) -> BacktestResult:
        results = [self._evaluate_one(u, genome) for u in self.universes]
        avg_score = round(sum(r.score for r in results) / len(results), 4)
        avg_return = round(sum(r.portfolio_return for r in results) / len(results), 4)
        avg_down = round(sum(r.downside for r in results) / len(results), 4)
        # Report picks from the first universe for display; score is the average.
        return BacktestResult(picks=results[0].picks, portfolio_return=avg_return,
                              downside=avg_down, score=avg_score)

    def _evaluate_one(self, universe: Universe, genome: Genome | None) -> BacktestResult:
        cos = universe.companies
        w = genome_factor_weights(genome)
        z_mos = _z([c.margin_of_safety for c in cos])
        z_roic = _z([c.roic for c in cos])
        z_debt = _z([c.debt_to_equity for c in cos])
        z_oey = _z([c.owner_earnings_yield for c in cos])
        scored = []
        for i, c in enumerate(cos):
            composite = (w["mos"] * z_mos[i] + w["roic"] * z_roic[i]
                         - w["debt"] * z_debt[i] + w["oey"] * z_oey[i])
            scored.append((composite, c))
        scored.sort(key=lambda x: x[0], reverse=True)
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
