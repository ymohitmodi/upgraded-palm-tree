"""Career & extraordinary-ability (EB-1A) knowledge — seeds for the Advisor.

Durable, public doctrine the Advisor recalls when working ambiguous goals like
"grow a senior SDE career" or "get EB-1 publications ready". Knowledge, not
rules: the LLM decides how to apply it per task.
"""
from __future__ import annotations

import re

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


# ── Advisor evolution: directive pool + rubric benchmark ─────────────────────
# Charter directives mutation can graft onto the advisor genome. Broad and varied
# so the Darwin-Gödel search keeps finding admissible gains instead of plateauing.
ADVISOR_DIRECTIVES = [
    "Ground every claim in a verifiable source; include the URL you would cite.",
    "When evidence is missing, CALL arxiv_search, news_search, or web_fetch to find it "
    "before drafting.",
    "Map every deliverable explicitly to the criterion or goal it satisfies.",
    "Attach a dated milestone to each recommendation (month + year, realistic).",
    "End every deliverable with exactly one SINGLE NEXT ACTION, concrete enough to do today.",
    "Quantify everything: counts, dates, dollar figures, percentiles — no vague claims.",
    "Draft the artifact itself (email, abstract, outline), not advice about drafting it.",
    "Prefer the most attainable evidence first: reviewing and judging before grand claims.",
    "Track a publication pipeline: venue, deadline, status, and next step per paper.",
    "Never fabricate credentials, citations, or metrics; flag every assumption explicitly.",
    "List the top risks with a mitigation each; kill weak claims before a critic does.",
    "Structure output with headed sections and bullet lists so evidence is auditable.",
    "Name specific target venues, committees, or programs — never generic categories.",
    "Compare the candidate against the bar reviewers actually apply; state where they fall short.",
    "Sequence actions by leverage: highest-impact, lowest-effort evidence first.",
    "Cite the exact standard or criterion text the evidence must satisfy.",
    "Give each artifact a definition of done — what makes it submission-ready.",
    "Prefer primary sources (official pages, filings, the paper itself) over commentary.",
]

_GROUNDING_RE = re.compile(r"https?://|arxiv\.org|doi\.org|\bsource\s*:", re.IGNORECASE)
_DATE_RE = re.compile(r"\b20\d{2}\b")
_NEXT_ACTION_RE = re.compile(r"next\s+(action|step)", re.IGNORECASE)
_STRUCTURE_RE = re.compile(r"(?m)^\s*(?:[-*#]|\d+\.)\s+\S")
_NUMBER_RE = re.compile(r"\b\d[\d,.%]*\b")
_GUARANTEE_RE = re.compile(r"guarante|will\s+be\s+approved|certain\s+approval", re.IGNORECASE)


def rubric_score(text: str) -> float:
    """Deterministic quality rubric for an advisory deliverable (0..1).

    Rewards what makes a dossier defensible — grounding (citable sources), dated
    milestones, a single next action, auditable structure, and specificity — and
    penalizes promise-language the constitution forbids. Every component is capped,
    so keyword stuffing saturates instead of paying (same anti-gaming stance as the
    investing factor reader)."""
    if not text or len(text.strip()) < 80:
        return 0.0
    grounding = min(len(_GROUNDING_RE.findall(text)), 5) / 5
    dates = min(len(_DATE_RE.findall(text)), 4) / 4
    action = 1.0 if _NEXT_ACTION_RE.search(text) else 0.0
    structure = min(len(_STRUCTURE_RE.findall(text)), 8) / 8
    numbers = min(len(_NUMBER_RE.findall(text)), 12) / 12
    score = (0.25 * grounding + 0.20 * dates + 0.15 * action
             + 0.20 * structure + 0.20 * numbers)
    if _GUARANTEE_RE.search(text):
        score -= 0.25
    return round(min(max(score, 0.0), 1.0), 4)


# Training suite (evolution fitness) and a DISJOINT held-out suite (`nyx eval`),
# so the standing evaluation is not contaminated by what evolution optimized on.
ADVISOR_SUITE = [
    "Draft a plan to get onto one security conference program committee this year, "
    "with evidence of qualification and a timeline.",
    "Turn a production vulnerability-scanning system into an open-source project with "
    "a defensible original-contribution claim; outline the launch and adoption evidence.",
]
ADVISOR_HELDOUT = [
    "Build the evidence file for the 'high remuneration' criterion from a senior "
    "engineer's compensation; list documents and a draft summary paragraph.",
    "Plan one scholarly article from applied security work: venue shortlist, abstract "
    "outline, and a submission timeline.",
]


class AdvisorBenchmark:
    """Callable fitness: run the candidate-genome advisor on a fixed suite and
    average the deliverable rubric. Offline the mock provider makes this
    deterministic; live, better doctrine → measurably better deliverables."""

    def __init__(self, tasks: list[str] | None = None):
        self.tasks = tasks or ADVISOR_SUITE

    def __call__(self, agent) -> float:
        scores = []
        for task in self.tasks:
            try:
                text = agent.run(task).text
            except Exception:  # noqa: BLE001 — a failed generation scores zero
                text = ""
            scores.append(rubric_score(text))
        return round(sum(scores) / max(len(scores), 1), 4)
