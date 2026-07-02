"""Solopreneur doctrine — what actually makes a one-person business succeed.

Distilled from the recurring lessons of the indie-founder canon (Paul Graham's
essays, MicroConf / Rob Walling's stair-step approach, Indie Hackers
post-mortems, Daniel Vassallo's portfolio-of-small-bets, calm-company writing):
solo businesses rarely die from bad code — they die from building things nobody
wants, having no distribution, and running out of runway or energy.

These principles are seeded into **long-term memory**, so every plan and build
the factory produces is shaped by them via recall — the dark factory prioritizes
like a business, not just an engineering pipeline.
"""
from __future__ import annotations

PRINCIPLES: list[tuple[str, list[str]]] = [
    ("Distribution decides survival: spend roughly half of all effort on marketing, "
     "SEO/content, and channels — a great product nobody finds is a failed product.",
     ["solopreneur", "distribution", "marketing"]),
    ("Solve one painful, frequent problem for a niche you can actually reach; "
     "narrow and urgent beats broad and mild.",
     ["solopreneur", "niche", "positioning"]),
    ("Charge money from day one — a payment is the only validation that counts; "
     "free signups are not a business.",
     ["solopreneur", "pricing", "validation"]),
    ("Prefer recurring revenue (subscriptions) — MRR compounds; one-off sales reset "
     "to zero every month.",
     ["solopreneur", "revenue", "mrr"]),
    ("Talk to users every week and build what they pull out of you, not what you "
     "push; kill features nobody asked to pay for.",
     ["solopreneur", "users", "validation"]),
    ("Validate before you build: landing page, waitlist, presale — demand first, "
     "code second; ship the smallest sellable slice in days, not months.",
     ["solopreneur", "mvp", "validation", "shipping"]),
    ("Stay default-alive: keep fixed costs near zero so time — not money — is the "
     "binding constraint; profitability over growth theater.",
     ["solopreneur", "costs", "runway"]),
    ("Track ONE metric per phase (visits → signups → paid → retention) and ignore "
     "vanity metrics; decisions come from that number.",
     ["solopreneur", "metrics", "focus"]),
    ("Retention beats acquisition: fix churn before scaling marketing — a leaky "
     "bucket wastes every new customer.",
     ["solopreneur", "retention", "churn"]),
    ("Build owned distribution as an asset: an email list, SEO/content that "
     "compounds, and building in public — rented reach (ads, algorithms) can vanish.",
     ["solopreneur", "audience", "distribution"]),
    ("Run a portfolio of small bets: ship cheap experiments, kill losers fast, and "
     "double down only where real traction appears.",
     ["solopreneur", "small-bets", "portfolio"]),
    ("Automate and productize operations so revenue is not tied to your hours — "
     "systems (this factory) are the leverage that makes one person scale.",
     ["solopreneur", "automation", "leverage"]),
    ("Price on value, not cost or courage: raise prices until customers push back; "
     "underpricing is the most common solo mistake.",
     ["solopreneur", "pricing", "value"]),
    ("Sell the outcome, not the tech: customers buy time saved and money made; "
     "every feature and page should state the benefit in the customer's words.",
     ["solopreneur", "copywriting", "positioning"]),
]


def seed_principles(memory) -> int:
    """Write the solopreneur doctrine into long-term memory. Returns count."""
    n = 0
    for text, tags in PRINCIPLES:
        lesson = memory.remember(text, kind="principle", tags=tags,
                                 source="solopreneur", weight=2.0)
        lesson.tier = "long_term"  # business doctrine is durable from day one
        n += 1
    memory._flush()
    return n
