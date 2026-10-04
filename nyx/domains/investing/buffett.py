"""Buffett / Berkshire knowledge — seed and grow NYX's value-investing memory.

Two paths:

1. ``seed_principles`` — write a curated set of deep-value tenets (distilled from
   Buffett's public shareholder letters) straight into long-term memory. This
   works **offline today**, so the analyst starts with a Buffett-shaped lens.

2. ``fetch_letters`` — when the network allows ``berkshirehathaway.com``, pull
   the actual annual shareholder letters and store sourced excerpts as long-term
   memories tagged by year, so recall can quote the primary source. Best-effort
   per URL; failures are skipped so the loop never stalls.

The letters index: https://www.berkshirehathaway.com/letters/letters.html
"""
from __future__ import annotations

# Curated, public deep-value tenets — the analyst's starting doctrine.
PRINCIPLES: list[tuple[str, list[str]]] = [
    ("Buy a wonderful company at a fair price, not a fair company at a wonderful price.",
     ["buffett", "investing", "quality"]),
    ("Always demand a margin of safety: pay meaningfully less than conservative intrinsic value.",
     ["buffett", "investing", "margin-of-safety"]),
    ("Stay within your circle of competence; only value businesses you truly understand.",
     ["buffett", "investing", "competence"]),
    ("Favor durable competitive advantages (moats): pricing power, low-cost, network, brand.",
     ["buffett", "investing", "moat"]),
    ("Prize high returns on invested capital (ROIC) achieved with little debt.",
     ["buffett", "investing", "roic", "quality"]),
    ("Judge management on capital allocation and candor; owner-oriented, rational, honest.",
     ["buffett", "investing", "management"]),
    ("Think in owner-earnings (cash a business can distribute), not reported accounting EPS.",
     ["buffett", "investing", "owner-earnings", "valuation"]),
    ("Read the footnotes: leases, pensions, stock comp, contingencies hide the real economics.",
     ["buffett", "investing", "footnotes", "risk"]),
    ("Be fearful when others are greedy and greedy when others are fearful.",
     ["buffett", "investing", "temperament"]),
    ("Price is what you pay; value is what you get. Volatility is opportunity, not risk.",
     ["buffett", "investing", "valuation", "temperament"]),
    ("The first rule is don't lose money; the second rule is don't forget the first.",
     ["buffett", "investing", "risk", "drawdown"]),
    ("Prefer simple, predictable businesses with long runways over complex turnarounds.",
     ["buffett", "investing", "predictability"]),
    ("A great business reinvests at high rates of return for many years — let it compound.",
     ["buffett", "investing", "compounding"]),
]


def seed_principles(memory) -> int:
    """Write the curated Buffett tenets into long-term memory. Returns count."""
    n = 0
    for text, tags in PRINCIPLES:
        lesson = memory.remember(text, kind="principle", tags=tags, source="buffett", weight=2.0)
        lesson.tier = "long_term"  # doctrine is durable from day one
        n += 1
    memory._flush()
    return n


def letter_urls(start: int = 1977, end: int = 2024) -> list[tuple[int, str]]:
    """Candidate shareholder-letter URLs by year (html for older, pdf for recent)."""
    urls: list[tuple[int, str]] = []
    for year in range(start, end + 1):
        if year <= 1997:
            urls.append((year, f"https://www.berkshirehathaway.com/letters/{year}.html"))
        else:
            urls.append((year, f"https://www.berkshirehathaway.com/letters/{year}ltr.pdf"))
    return urls


_LETTER_FOCUS = ("what makes a business wonderful (moats, pricing power, returns on "
                 "capital), how to judge management and capital allocation, valuation "
                 "and owner-earnings, temperament, and the mistakes to avoid; and "
                 "critically, WHY specific investments were bought or sold at the "
                 "prices then prevailing — what made the chosen business better than "
                 "its direct competitors and alternatives at that moment, how cheaply "
                 "it was bought relative to its earning power, and what would have "
                 "changed the decision")


def fetch_letters(fetcher, memory, *, years: list[int] | None = None,
                  start: int = 1977, end: int = 2024, config=None, provider=None,
                  max_lessons: int = 5) -> dict:
    """Read Berkshire letters the way a student of Buffett would: the WHOLE letter,
    then distilled into durable investing PRINCIPLES — not a stored excerpt or a
    figures dump.

    Each letter is an authoritative primary source, so its injection-screened
    lessons become long-term doctrine (deduped/reinforced across decades) via
    :func:`nyx.context.read_and_learn`. ``years`` reads a specific batch — so a long
    run can work through all 45 letters without blowing one cycle's budget; omit it
    to read the whole ``start..end`` range. Returns {fetched, skipped, principles}.
    """
    from ...context import read_and_learn

    todo = [(y, u) for y, u in letter_urls(start, end)
            if years is None or y in set(years)]
    fetched = skipped = principles = 0
    for year, url in todo:
        try:
            doc = fetcher.fetch(url)
            body = (doc.text or "").lstrip()
            if (not (200 <= doc.status < 300) or len(body) < 400
                    or body.startswith("%PDF")
                    or doc.text.count("�") > max(20, len(doc.text) // 20)):
                skipped += 1
                continue
            _, _, new_principles = read_and_learn(
                memory, doc.text, source=f"Berkshire {year} letter ({url})",
                tags=["buffett", "letter", str(year)], focus=_LETTER_FOCUS,
                config=config, provider=provider, doctrine=True, max_lessons=max_lessons)
            principles += new_principles
            fetched += 1
        except Exception:  # noqa: BLE001 — best effort; never stall the loop
            skipped += 1
    memory._flush()
    return {"fetched": fetched, "skipped": skipped, "principles": principles}
