"""Career & extraordinary-ability (EB-1A) knowledge — seeds for the Advisor.

Durable, public doctrine the Advisor recalls when working ambiguous goals like
"grow a senior SDE career" or "get EB-1 publications ready". Knowledge, not
rules: the LLM decides how to apply it per task.
"""
from __future__ import annotations

PRINCIPLES: list[tuple[str, list[str]]] = [
    # Senior+ engineering career
    ("Seniority is scope: promotion follows sustained impact beyond your team — own "
     "problems no one assigned, and land cross-team outcomes with measurable results.",
     ["career", "sde", "promotion", "scope"]),
    ("Keep a brag document: log every impact with metrics the week it happens; reviews "
     "and packets are assembled from evidence, not memory.",
     ["career", "sde", "brag-doc", "evidence"]),
    ("Visibility is engineered: design docs, tech talks, postmortems, and mentoring "
     "create the paper trail that calibration committees actually read.",
     ["career", "sde", "visibility"]),
    ("Pick strategic projects: high-leverage, business-critical, visible-to-leadership "
     "work beats twice the effort on invisible maintenance.",
     ["career", "sde", "strategy", "projects"]),
    ("Grow through multipliers: mentoring, standards, tooling, and hiring scale your "
     "impact past what you can personally type.",
     ["career", "sde", "leadership", "multiplier"]),
    # EB-1A / extraordinary ability evidence building
    ("EB-1A needs at least 3 of 10 criteria; the realistic engineer path is judging "
     "(peer review, hackathons, program committees), original contributions, "
     "publications/scholarly articles, critical role, high remuneration, and press.",
     ["eb1", "immigration", "criteria"]),
    ("Publications compound: turn production work into IEEE/ACM/industry-journal papers "
     "and conference talks; each also creates citations, judging invites, and press hooks.",
     ["eb1", "publications", "career"]),
    ("Citations and adoption are the evidence of 'original contribution' — open-source "
     "your frameworks, write the definitive posts, and track who uses and cites them.",
     ["eb1", "citations", "open-source", "contributions"]),
    ("Become a judge of others' work early: review for journals/conferences, judge "
     "hackathons, serve on program committees — it is the most attainable criterion.",
     ["eb1", "judging"]),
    ("Document everything contemporaneously: letters, metrics, press, membership "
     "criteria — a strong petition is an evidence-collection habit, not a scramble.",
     ["eb1", "evidence", "documentation"]),
]


def seed_principles(memory) -> int:
    n = 0
    for text, tags in PRINCIPLES:
        lesson = memory.remember(text, kind="principle", tags=tags, source="career", weight=2.0)
        lesson.tier = "long_term"
        n += 1
    memory._flush()
    return n
