# EB-1A Playbook — AI / Senior Security Engineer

A PhD-depth operating playbook for a senior AI security engineer building an
EB-1A ("extraordinary ability") petition. It encodes the legal standard, the
evidentiary criteria as an engineer can actually satisfy them, and a
multi-quarter execution plan. This is knowledge for planning and drafting — not
legal advice; a qualified immigration attorney signs the strategy.

## The legal standard and how adjudication actually works

EB-1A requires demonstrating "sustained national or international acclaim" and
being among "the small percentage at the very top" of the field. Since the 2010
Kazarian v. USCIS decision, adjudication is a TWO-STEP analysis, and conflating
the steps is the most common petition failure. Step one is a COUNTING exercise:
you must satisfy at least 3 of the 10 regulatory criteria (8 CFR 204.5(h)(3))
with qualifying evidence — here the officer only asks "does this evidence meet
the plain language of the criterion?", not "is it impressive?". Step two is a
FINAL MERITS DETERMINATION: stepping back, does the TOTALITY of evidence show
you are actually at the top of the field with sustained acclaim? A petition can
count 4 criteria and still fail step two if the evidence is thin, stale, or
field-marginal. Everything in this playbook is engineered to win BOTH steps:
satisfy criteria on plain language, then assemble them into a coherent narrative
of a person the field recognizes as extraordinary. The evidentiary bar is
"preponderance of the evidence" (more likely than not), not beyond doubt — but
officers are trained to discount conclusory letters and unverifiable claims, so
independent, corroborated, documentary evidence beats assertion every time.

## Criterion — Judging the work of others

One of the most attainable criteria for an engineer and the fastest to start.
The plain language: evidence that you have judged, individually or on a panel,
the work of others in the same or an allied field. What qualifies and how to
build it deliberately: peer review for reputable venues (program committees of
security conferences — IEEE S&P, USENIX Security, ACM CCS, NDSS — and AI/ML
venues NeurIPS, ICML, ICLR; journal reviewing for IEEE TDSC/TIFS); judging
hackathons and CTFs; serving as a grant or award reviewer. Evidence to preserve
contemporaneously: the reviewer invitation email, the venue's acceptance/thank-you,
completed review records or the reviewer dashboard, and confirmation of the
venue's selectivity and standing. Depth that impresses at step two: review for
SELECTIVE, well-known venues (not predatory or pay-to-review), do it repeatedly
across years (sustained, not one-off), and reach program-committee or
area-chair level. Start now: reviewing invitations flow to anyone with relevant
publications or a strong GitHub/industry profile who signals availability to
program chairs; volunteering for artifact-evaluation committees is an accessible
on-ramp.

## Criterion — Original contributions of major significance

The heaviest criterion and the hardest to prove, because "major significance"
demands evidence of IMPACT, not just novelty. For an AI security engineer the
qualifying contributions include: a novel attack or defense that the field
adopted (e.g., a new class of model-extraction or prompt-injection defense);
an open-source security framework or tool with demonstrable adoption; a CVE of
broad impact with documented downstream remediation; a standard or best-practice
you authored that others follow. The proof is external and documentary:
citation records (Google Scholar with h-index and per-paper counts), adoption
metrics (GitHub stars/forks/dependents, package download counts, enterprises
using the tool by name), inclusion of your method in later products or standards,
media and analyst coverage, and — decisively — INDEPENDENT expert letters that
explain the "before and after" your work created in concrete technical terms.
The letter-writing strategy: mix "dependent" recommenders (people who know you)
with a MAJORITY of "independent" experts who know your work but not you
personally; each letter must be specific ("her differential-privacy library is
now the default in three Fortune-500 ML pipelines, replacing X") rather than
adulatory. Weak significance evidence — "novel and interesting" without adoption
— is the classic step-two killer.

## Criterion — Scholarly articles and authorship

Plain language: authorship of scholarly articles in professional journals or
major trade publications with a national/international audience. For a security
engineer the qualifying outlets are broader than pure academia: peer-reviewed
conference proceedings (in CS the proceedings ARE the archival record and count),
IEEE/ACM journals, USENIX ;login:, and substantive industry venues. Build:
convert production research into papers — a novel detection technique, a
measurement study of a threat, a systematization-of-knowledge paper (SoK papers
are high-impact and very citable). Evidence: the publications themselves, venue
descriptions establishing rigor and reach, and citation counts. Quality over
count: three well-cited papers at top venues beat fifteen at obscure ones, and
citation velocity (cited quickly by independent groups) is the signal officers
and letter-writers can point to. Authorship position matters less in CS than in
bench science, but first/corresponding authorship strengthens the "original
contribution" link.

## Criteria — Awards, memberships, high remuneration, leading/critical role

Four criteria an experienced engineer can often satisfy with existing career
evidence, assembled correctly. AWARDS: nationally/internationally recognized
prizes for excellence — competitive CTF placements, best-paper awards, bug-bounty
hall-of-fame and top-tier bounty payouts (documented), significant hackathon
wins; the award's SELECTIVITY and reputation must be documented, not assumed.
MEMBERSHIP in associations requiring outstanding achievement judged by experts —
most professional bodies (IEEE member grade) do NOT qualify; IEEE SENIOR MEMBER
(requires nomination and peer review) can, as can invitation-only bodies.
HIGH REMUNERATION: compensation in the top percentile for the field — prove with
your offer/comp letters PLUS objective wage data (BLS OES, levels.fyi, DOE wage
levels, published surveys) showing your total comp sits at the top of the
distribution for security engineers in your geography; RSUs and bonuses count
when documented. LEADING OR CRITICAL ROLE for organizations with a distinguished
reputation: prove the ORGANIZATION's standing (press, funding, market position)
AND your criticality (org chart, a letter from leadership stating the outcomes
you owned, launches/incidents you led) — "senior engineer at a famous company"
is not enough; the evidence must show YOU were critical, not merely employed.

## Criteria — Media coverage, exhibitions, commercial success

Rounding out the ten. PUBLISHED MATERIAL ABOUT YOU in professional or major
media relating to your work: conference talk write-ups, podcast/press features,
articles discussing your tool or research (about YOU/your work, with title,
date, author, and outlet circulation documented — not incidental mentions).
DISPLAY at exhibitions/showcases maps awkwardly to software but can be argued via
invited talks and demos at flagship venues (Black Hat/DEF CON stage,
keynote/invited status). COMMERCIAL SUCCESS is hard for engineers unless you have
a product with documented revenue tied to your work. For most AI-security
petitions the winning THREE-to-FOUR are: judging + original contributions +
scholarly articles, reinforced by high remuneration and/or critical role.

## The publication and citation engine (execution)

Publications are the flywheel that spins the other criteria: each paper creates
citations (significance), review invitations (judging), and press hooks (media).
The engineer's pipeline: (1) mine current production work for a defensible
research claim — a new attack surface, a defense with measured efficacy, or a
measurement study only your vantage point enables; (2) target the right venue by
acceptance norms and audience, preferring selective security/ML venues and SoK
tracks; (3) open-source the artifact alongside the paper (artifacts drive
citations and adoption evidence simultaneously); (4) promote for citation
velocity — talks, blog write-ups, social, and building-in-public — because early
independent citations are the step-two signal; (5) convert readership into
judging invitations by signaling availability to program chairs. Realistic
cadence: one substantial paper plus one SoK/workshop paper per year, each with a
maintained open-source artifact, compounds within 18–24 months into a citable
body of work plus a reviewing record.

## Evidence architecture and the petition dossier

A strong petition is an EVIDENCE-COLLECTION HABIT, not an end-of-process scramble.
Maintain a living dossier organized by the ten criteria, and file evidence the
week it is created: invitations and completion records (judging); citation
exports and adoption metrics with dated screenshots (significance); publications
with venue-standing documentation; comp letters plus wage-survey citations;
org-standing press plus role/criticality letters; media clippings with outlet
circulation. Recommendation letters are drafted LAST, from this evidence: 5–7
letters, a MAJORITY from independent experts, each tightly mapped to specific
criteria and written in concrete technical language the expert can defend. Build
the petition around a one-paragraph THESIS ("X is among the small percentage at
the top of AI security, evidenced by [criteria], demonstrating sustained acclaim
through [timeline]"), then let every exhibit serve that thesis. Anticipate the
Request for Evidence: pre-empt the common challenges (independence of letter
writers, significance vs. mere novelty, selectivity of venues/awards) with
documentary proof inside the initial filing. Note the parallel NIW (EB-2 National
Interest Waiver) path as a strategic hedge — a lower bar (Dhanasar three-prong)
that AI-security work often fits, sometimes filed concurrently — but EB-1A, when
winnable, offers faster priority-date movement and no labor certification.

## Timeline, sequencing, and pitfalls

A realistic build from a standing start is 18–36 months, sequenced so evidence
compounds. Quarters 1–2: start reviewing (judging on-ramp), submit the first
paper, open-source the flagship artifact, begin the dossier, and gather wage
data. Quarters 3–4: land publications, accumulate citations, escalate to program
committees, pursue IEEE Senior Member, document critical-role outcomes. Quarters
5–6: solicit independent letters from people now citing your work, assemble
exhibits by criterion, engage counsel, draft the thesis and petition. Pitfalls
that sink otherwise-strong candidates: treating step one's counting as
sufficient and neglecting the step-two narrative; leaning on dependent
letter-writers; claiming significance without adoption evidence; using predatory
venues that officers recognize and discount; letting evidence go stale ("acclaim"
must be SUSTAINED and current); and conflating seniority/tenure with
extraordinary ability — a Principal title proves employment, not acclaim. The
antidote to all of them is contemporaneous, independent, documentary evidence
assembled into a coherent story of someone the field visibly recognizes.
