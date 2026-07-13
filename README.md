# NYX — The Autonomous Dark Factory

> A constitutional, self‑evolving, multi‑agent **dark factory** that turns one
> plain‑language objective into continuous, compounding, self‑improving work —
> for **software, deep‑value investing, or an ambiguous career/EB‑1 goal** —
> running on an **Ollama Cloud** brain, lights‑out, from a single mini‑PC.

NYX (the Greek goddess of night — the *lights‑out* factory) is an agentic
operating system for the **solopreneur of the autonomous era**. One human sets
the intent; a swarm of specialized AI agents plans, acts (with tools), gates
every step against a Constitution, remembers what it learns, and **evolves to
get better** — without babysitting.

```bash
nyx run "Find deep-value public companies for a 20% CAGR; learn from Buffett; \
keep reading SEC filings and Berkshire reports" --keep-going --autonomy autonomous
```

One command. It routes to the right capability, plans a backlog, reads full
filings without losing context, decides, reflects into long‑term memory,
evolves its agents against a real benchmark, consolidates ("sleep"), and repeats
— every action written to a tamper‑evident audit ledger.

### What NYX is great at (and what it isn't)

NYX is **not** a smarter chatbot — it rides on top of an LLM. Its edge is a
*different axis*: **unattended continuity + governance**. A chat app is a
brilliant advisor with amnesia and no hands; NYX remembers across months, acts
on a schedule, reads live sources, evolves, and logs everything. Use a chat app
to *think*; use NYX to *keep executing* long‑horizon, evidence‑compounding goals
(an EB‑1 dossier, a monitored value screen, a shipping backlog). For one‑shot
drafting or in‑editor coding, use the chat app.

It is built on three convictions:

1. **Dark Factory** — software should build, test, and ship itself with the
   human supervising *outcomes*, not keystrokes. (See [Dark Factory pattern](https://aipatternbook.com/dark-factory).)
2. **Constitution before capability** — every agent is bound by a
   machine‑readable [Constitution](constitution/constitution.yaml) inspired by
   [Anthropic's Constitutional AI](https://www.anthropic.com/research/constitutional-ai-harmlessness-from-ai-feedback)
   and the engineering doctrines of the world's best software companies. Safety,
   security, and quality are *constructed in*, not bolted on.
3. **Evolution, not stagnation** — agents improve their own prompts, tools, and
   workflows using a [Darwin‑Gödel](https://arxiv.org/abs/2505.22954) style
   archive: a variant is kept only if it empirically beats its ancestor.

---

## Why this exists

By mid‑2026, frontier and strong open‑weight models crossed the capability
threshold for autonomous software work. Teams report **3–5× throughput** running
structured agent factories instead of AI autocomplete. NYX packages that shift
into something a single founder can run from a mini‑PC:

```
        ┌──────────────────────────────────────────────────────┐
        │                  ONE HUMAN  (intent)                  │
        └───────────────────────────┬──────────────────────────┘
                                     │  goals, constraints, taste
                                     ▼
   ┌───────────────────────────  NYX FACTORY  ───────────────────────────┐
   │  Explore → Design → Build → Review → Test → Ship → Operate → Evolve  │
   │     (fan‑out swarms of constitutional agents, supervised by gates)    │
   └─────────────────────────────────┬───────────────────────────────────┘
                                      ▼
                         Ollama Cloud  (the brain)
                      Windows 11 mini‑PC  (the body)
```

## Pillars

| Pillar | What it means in NYX | Module |
| --- | --- | --- |
| **One autonomous loop, LLM‑routed** | Objective → route → plan → act → gate → reflect → recall → evolve → consolidate → repeat | [`nyx/capabilities/runner.py`](nyx/capabilities/runner.py) |
| **Pluggable capabilities** | `software`, `value‑investing`, `advisor` (careers/EB‑1) — drop in a `Capability` and it inherits the whole stack | [`nyx/capabilities`](nyx/capabilities) |
| **Dark Factory + Fan‑Out** | Gated SDLC pipeline; many agents work a stage, the best wins | [`nyx/factory`](nyx/factory) |
| **Agentic tool use** | Agents call tools (web/EDGAR/`read_url`) mid‑task via a guardrailed ReAct loop | [`nyx/agents/base.py`](nyx/agents/base.py) |
| **Self‑Evolving Agents** | Darwin‑Gödel archive; a variant is adopted only if it beats its ancestor | [`nyx/evolution`](nyx/evolution) |
| **Memory + "sleep"** | Episodic + procedural + semantic; reflect → recall → **consolidate** into long‑term principles | [`nyx/memory.py`](nyx/memory.py) |
| **Semantic recall** | Cosine similarity over embeddings (offline hashing or live) | [`nyx/embeddings.py`](nyx/embeddings.py) |
| **Long‑document context** | Read a full 10‑K without overflow (refine‑fold + retrieval) | [`nyx/context.py`](nyx/context.py) |
| **Deep skills** | PhD‑level packs (Buffett/Graham, EB‑1A, frontier‑AI) ingested per‑section into memory | [`nyx/skill_packs`](nyx/skill_packs) |
| **Real benchmarks** | SWE‑bench‑style code execution + point‑in‑time value backtest | [`nyx/domains/investing`](nyx/domains/investing) |
| **State‑of‑the‑art AI security** | Constitution + LLM injection classifier + SSRF/egress guard + least‑privilege typed tools + sandbox + secret hygiene (OWASP LLM Top 10) | [`nyx/security`](nyx/security) |
| **Constitutional governance** | 17 principles (incl. least‑privilege, safe egress, evolve‑within‑rules) enforced on every call; hash‑chained audit ledger | [`constitution/constitution.yaml`](constitution/constitution.yaml) |
| **Tools & connectivity** | Web crawl, SEC EDGAR/XBRL, MCP servers (`nyx mcp-init`) | [`nyx/tools`](nyx/tools) |
| **Ollama Cloud brain** | One config, any frontier‑class cloud model | [`nyx/providers/ollama_cloud.py`](nyx/providers/ollama_cloud.py) |

## Install

### Windows 11 (PowerShell) — copy/paste

Python 3.10+ required (a Miniconda `base` Python is fine). From the repo root:

```powershell
# 1. Create a venv and install the full stack (live provider + SEC EDGAR + PDF + dev)
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[http,yaml,investing,dev]"

# 2. Windows console must use UTF-8 (NYX prints ✓/✗); make it permanent:
[Environment]::SetEnvironmentVariable("PYTHONUTF8", "1", "User")
$env:PYTHONUTF8 = "1"          # for the current session too

# 3. Config
Copy-Item .env.example .env    # then edit .env (see "Going live" below)

# 4. Register the SEC EDGAR MCP server (edgartools — no Docker) and check health
nyx mcp-init
nyx doctor
```

> The bundled `scripts/setup-windows11.ps1` automates steps 1–4 (it also installs
> Git/Python via winget if missing). If you already have a working Python, the
> manual steps above are all you need.

### Linux / macOS — one-shot installer

Creates a venv, installs everything, seeds skills, runs doctor + preflight + tests:

```bash
./install.sh                 # full: venv + investing extras + dev + tests
./install.sh --minimal       # core only (mock mode, zero extra deps)
```

**Or install manually** — the core is dependency-free (mock mode needs nothing):

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .                       # minimal (mock mode)
pip install -e ".[investing,dev]"      # or full: live provider + SEC EDGAR + tests
cp .env.example .env                    # every value has a safe default
```

Going live (keys + data): edit `.env`, then `nyx preflight --probe` and the
[runbook](docs/RUNBOOK.md).

## Quick start

```bash
# Hand NYX an OBJECTIVE and let it run autonomously (mock mode works offline):
#   route -> plan -> act (tools) -> gate (all verified) -> reflect -> evolve -> repeat
nyx run "Launch a SaaS analytics product" --autonomy autonomous --keep-going
nyx run "Find deep-value companies; learn from Buffett" --autonomy autonomous

# Deep-value investing: screen the WHOLE US market today, read finalists' full
# 10-Ks into memory, rank by conviction (see "Deep-value investing" below):
nyx screen --top 10

# One feature through the full gated pipeline:
nyx build "Add a usage-based billing dashboard with Stripe metering"

# Evidence surfaces (the trust artifacts):
nyx eval             # held-out score trend — did it get better?
nyx track            # realized-outcome track record
nyx ledger --tail 20 # tamper-evident audit trail
nyx security-audit   # OWASP LLM Top 10 + Agentic-threat posture
```

> **Windows:** run these with the venv active (`.\.venv\Scripts\Activate.ps1`).
> To pass a long objective in PowerShell, put it in a here-string first — see
> [Deep-value investing](#deep-value-investing-nyx-run--nyx-screen).

## "If I give it an objective, will it keep going, stay productive, and evolve?"

**Yes — that's what `nyx run` does.** Hand it one objective and the
[capability runner](nyx/capabilities/runner.py) closes the loop:

```
objective ─▶ PLAN (decompose into a backlog of shippable features)
          ─▶ for each feature: run the DARK FACTORY pipeline (gated, audited)
          ─▶ every K cycles: run DARWIN evolution (admit a variant only if it
             beats its ancestor on the benchmark)
          ─▶ ADOPT the improved genome so later cycles run on better agents
          ─▶ repeat until the backlog drains (or with --keep-going, re-plan
             and continue) — bounded by the call budget and the constitution
```

So a single objective produces continuous, compounding output: it ships
features **and** the agents shipping them get measurably better as the mission
runs (and the gains persist across missions via the evolution archive). Every
step is constitution-gated and written to the tamper-evident audit ledger, so
"keeps going" never means "runs unchecked."

## "How does it remember and learn?"

NYX learns on **three memory substrates** that reinforce each other (full
detail in [docs/MEMORY.md](docs/MEMORY.md)):

| Layer | Answers | Lives in |
| --- | --- | --- |
| **Episodic** | *What happened?* | hash‑chained [audit ledger](nyx/observability/ledger.py) |
| **Procedural** | *How do we get better at the job?* | [evolution archive](nyx/evolution/archive.py) (improved agent genomes) |
| **Semantic** | *What did we learn to reuse?* | [memory store](nyx/memory.py) (distilled lessons) |

After every run the factory **reflects** — distilling lessons (a blocked gate →
a guardrail rule, a finding → a risk note, a clean ship → a reinforced pattern)
— **remembers** them, and on the next task **recalls** the relevant ones and
injects them into every agent's prompt. Meanwhile evolution banks better agents,
and the ledger keeps the full record:

```
execute → REFLECT → REMEMBER → RECALL next time → better execution
         ↘ EVOLVE (better agents, adopted back in) ↗
```

It also works like a brain in two more ways: **working memory** is bounded
(context is compacted between stages, prompts stay within a budget), and a
periodic **consolidation "sleep" pass** decays unused lessons, abstracts
recurring ones into stable long‑term *principles*, and forgets the rest — so
proven, general knowledge outcompetes one‑off notes over time.

No vector DB, no retraining — it runs offline on the mini‑PC. `nyx memory`
shows what it has learned; `nyx memory --consolidate` runs a sleep pass.

No API key? NYX runs in **deterministic mock mode** so you can explore the whole
factory offline. Add an Ollama key to `.env` to switch the brain on.

## Deep-value investing (`nyx run` / `nyx screen`)

NYX ships a real deep-value pipeline over **live SEC data** — every number sourced
from filings, the whole US market as the universe, and full 10-Ks read end-to-end.

**How it works — a funnel** (real analysts don't read all 8,000 10-Ks; they screen
wide, then read deep):

1. **Screen the whole market, cheaply.** SEC's bulk XBRL *frames* API returns one
   fundamental for *every* filer in a single call, so ~7 calls cover ~4,600
   companies in seconds. NYX ranks them price-free on **quality** (return on
   assets, owner-earnings, low leverage) and keeps the top `NYX_SCREEN_WIDE`.
2. **Value the survivors.** Fetch real prices (Yahoo) → market cap → margin of
   safety, and rank by the **evolved** analyst's factor weights.
3. **Read the finalists in full.** For the top `NYX_SCREEN_DEEP`, read the *entire*
   latest 10-K (all items — Business, Risk Factors, MD&A, footnotes; ~300k chars →
   ~130 chunks) through NYX's [long-document engine](nyx/context.py) — chunked,
   folded, embedded, **nothing truncated** — plus footnotes / 8-K / Form 4 insider
   trades / a bellwether **13F** via the [edgartools MCP server](nyx/tools/mcp.py).
4. **Judge.** The analyst scores each finalist 0–10 with a rationale, weighing the
   filings, the Buffett doctrine in memory, and 13F ownership; the final rank blends
   that conviction with the value factors.

### One-shot current screen — `nyx screen`

Applies the evolved analyst to **today's** fundamentals and prints a shortlist:

```powershell
.\.venv\Scripts\Activate.ps1
$env:PYTHONUTF8 = "1"
$env:NYX_SCREEN_WIDE = "500"   # value the top-N quality names from the whole market
$env:NYX_SCREEN_DEEP = "25"    # read the FULL 10-K of the top-N finalists into memory
nyx screen --top 10
```

### Autonomous run — screens **and** evolves — `nyx run`

`nyx run` now does everything in one command: it evolves the analyst against a
walk-forward backtest **and** runs the whole-market funnel, forging what it reads
into long-term memory. In PowerShell, pass the objective via a here-string (no
backslashes — those are Bash line-continuations and will error):

```powershell
.\.venv\Scripts\Activate.ps1
$env:PYTHONUTF8 = "1"
$env:NYX_SCREEN_WIDE = "1000"    # top-1000 quality names advance to valuation
$env:NYX_SCREEN_DEEP = "50"      # full 10-Ks of the top-50 finalists read into memory

$obj = @'
Find deeply undervalued, financially sound public companies to maximize long-term risk-adjusted return with a strict margin of safety. Read full SEC filings including footnotes; compute owner earnings, ROIC, leverage, and a conservative intrinsic value from filings. Shortlist the most undervalued names, research recent news, and rank by risk-adjusted expected return. Apply the Buffett doctrine; reflect outcomes into memory and evolve the analyst against a walk-forward backtest. Keep going.
'@
nyx run $obj --autonomy autonomous --keep-going
```

Watch it live in a second terminal:

```powershell
Get-Content .nyx\audit.ledger.jsonl -Wait -Tail 5   # market_screen → universe → deep_read → screen_today → adopt_genome
```

### Investing knobs (environment variables)

| Variable | Default | Meaning |
| --- | --- | --- |
| `NYX_SCREEN_WIDE` | `120` | How many top-quality names advance from the whole-market screen to valuation. |
| `NYX_SCREEN_DEEP` | `15` | How many finalists get their **entire** 10-K read into memory. |
| `NYX_DEEP_READ_LLM` | `0` | `1` = distill each 10-K chunk with the model (richer, but ~130 calls/company); default is the free deterministic fold. |
| `NYX_INVEST_TICKERS` | — | Comma-separated watchlist to force a specific universe (skips the market screen). |
| `NYX_13F_MANAGERS` | `BRK-B` | Comma-separated 13F filers whose holdings are cross-referenced as a signal. |

**Practical limits (honest):** valuation is capped at ~500 names per pass, and
`NYX_SCREEN_DEEP=50` full 10-K reads take ~20–40 min. Start with `WIDE=500,
DEEP=25` to confirm end-to-end, then scale up. NYX is still a **factor model** at
its core — the filings/news/13F enrich the analyst's judgment and memory, they
don't (yet) mechanically rewrite the intrinsic-value formula.

**Prove it's learning:** `nyx eval` (held-out score trend — run it repeatedly),
`nyx memory` (lessons forged from filings), and the ledger's `adopt_genome`
(evolution found a better analyst) vs `reject_no_gain` (a plateau) entries.

## Long-horizon research & advisory objectives (EB-1A, publications, patents)

Any objective — not just software or investing — gets the full self-evolving
treatment. Career/EB-1A/research goals route to the **advisor** capability, which:

- **Researches continuously**: every cycle pulls the current **arXiv** literature
  and **news** on queries derived from your objective (plus anything reachable via
  `web_fetch`/`read_url` and registered MCP servers), storing it as untrusted
  research memory the next cycle recalls.
- **Evolves**: the advisor genome is scored by a deterministic deliverable rubric
  (grounded sources, dated milestones, one concrete next action, auditable
  structure, specificity — promise-language penalized) and a variant is adopted
  only if it beats its ancestor. `nyx eval` tracks the held-out trend.
- **Writes a living dossier**: every gated deliverable lands in `.nyx/dossier/`
  as a dated markdown artifact, so months of work accumulate in files.

```powershell
.\.venv\Scripts\Activate.ps1
$env:PYTHONUTF8 = "1"

$obj = @'
I am a Senior Security Engineer at AWS Amazon Inspector in Austin (9 years at Amazon, total comp ~350k, cloud vulnerability-management domain). Build my EB-1A extraordinary-ability case. Produce a prioritized, dated plan and concrete draft artifacts to satisfy at least 4 of the 10 criteria: judging others' work (program committees, artifact evaluation, journal reviewing); original contributions (open-source my scanning work with adoption evidence); scholarly articles (publication + SoK pipeline for top security venues); high remuneration and critical-role evidence. For each criterion output the evidence needed, a draft, and the single next action, in a living dossier organized by criterion. Ground every claim; never fabricate citations or credentials. Keep going and refine.
'@
nyx run $obj --autonomy autonomous --keep-going

# Artifacts:  Get-ChildItem .nyx\dossier        # the living dossier
# Evolution:  nyx eval                          # advisor's held-out rubric trend
```

Every advisor plan **leads with a research radar** — a living
`dossier/00-research-radar.md` listing what's HOT right now, the open **white
space** worth claiming, and concrete publication targets, each grounded in
today's fetched arXiv/news titles. Deliverables are **multipass-refined**
(draft → skeptical critique → revision, keeping the better version) and scored
by a deliverable rubric that also drives evolution.

### MCP server factory — add tools without code

`nyx mcp-init` is a factory: name servers from the catalog and each registers as
an `mcp.<name>` tool that agents pick up automatically.

```powershell
nyx mcp-init --list                                        # the catalog
nyx mcp-init --add edgartools,paper-search,web-researcher  # additive merge
# Catalog: edgartools (SEC), paper-search (arXiv/PubMed papers),
#          web-researcher (deep web), hexstrike-ai (AI-security, authorized use).
```
Then install the server binaries you enabled (`uvx paper-search-mcp`,
`npx web-researcher-mcp`, etc.) — NYX calls them via `mcp.<name>` under each
capability's least-privilege allowlist.

Research tools available to every agent: `arxiv_search` (relevance-ranked papers),
`news_search` (Google News), `web_fetch`/`web_crawl`/`read_url` (full-document
reads), and any `mcp.*` server you register. For patents, allowlist
`patents.google.com` and let the advisor `read_url` patent pages. The default
`.env` allowlist already includes `arxiv.org`, `export.arxiv.org`,
`news.google.com`, `patents.google.com`, and `uscis.gov`.

### Run for hours or days — compounding learning

```powershell
# Lights-out: unlimited cycles, 24h wall clock, 5000-call budget. It re-plans
# when the backlog drains, evolves every 2 cycles, consolidates memory, and
# every artifact lands in .nyx\dossier\ while genomes bank in the archive.
nyx run $obj --autonomy autonomous --keep-going --max-cycles -1 --hours 24 --max-calls 5000

# Watch it learn (second terminal):
Get-Content .nyx\audit.ledger.jsonl -Wait -Tail 5   # dossier_write / adopt_genome / research
nyx memory --capability advisor                      # this domain's lessons only
nyx eval                                             # held-out trend: is it getting wiser?
```

Memory is **compartmentalized per capability** (`memory-advisor.jsonl`,
`memory-value-investing.jsonl`, …) so domains never pollute each other's recall;
`nyx memory` lists the partitions.

## Running on a Windows 11 mini‑PC

The whole factory is designed to live on a fanless mini‑PC humming in a corner.
See [`docs/DEPLOYMENT_WINDOWS11.md`](docs/DEPLOYMENT_WINDOWS11.md) and the
one‑shot installer [`scripts/setup-windows11.ps1`](scripts/setup-windows11.ps1).

## Documentation

- [Vision](docs/VISION.md) — the solopreneur dark factory thesis
- [Architecture](docs/ARCHITECTURE.md) — how the swarm is wired
- [Constitution](constitution/constitution.yaml) — the DNA
- [Security model](docs/SECURITY.md) — secure‑AI guarantees
- [Capabilities](docs/CAPABILITIES.md) — pluggable goal-specific autonomy (e.g. value investing)
- [Evolution](docs/EVOLUTION.md) — how agents improve themselves
- [Evaluation](docs/EVALUATION.md) — held-out score trend (`nyx eval`), proof it compounds
- [Memory & learning](docs/MEMORY.md) — how the factory remembers and gets wiser
- [Context management](docs/CONTEXT.md) — reading full 10-Ks without overflow
- [Critique & roadmap](docs/CRITIQUE.md) — an honest look at what's real vs. proxy
- [Benchmark (honest)](docs/BENCHMARK.md) — can it beat frontier models / PhDs? where yes, where no
- [Limitations by design](docs/LIMITATIONS.md) — LLM/harness limits and the controls around them
- [Security model](docs/SECURITY.md) — OWASP LLM Top 10 + Agentic threats (`nyx security-audit`)
- [Go-live runbook](docs/RUNBOOK.md) — take a capability live (`nyx preflight`)
- [Tools, MCP & web access](docs/TOOLS.md) — equipping NYX with EDGAR/MCP/scraping
- [Windows 11 deployment](docs/DEPLOYMENT_WINDOWS11.md)

## Going live

Set these in `.env` (or as environment variables). **A real `.env` overrides its
own blank defaults**, so put your key in `.env` or export it — the value in the
process environment wins:

```ini
# The brain — an Ollama Cloud key switches NYX out of mock mode.
OLLAMA_API_KEY=sk-...                    # blank = deterministic MOCK mode
# Model routing (bare ids on ollama.com — NO `-cloud` suffix). Verify against
# your account (GET https://ollama.com/v1/models) and swap any retired ones.
# deepseek-v4-flash everywhere: 1M context (whole filings fit), fast parsing.
NYX_MODEL_ARCHITECT=deepseek-v4-flash
NYX_MODEL_CODER=deepseek-v4-flash
NYX_MODEL_REVIEWER=deepseek-v4-flash
NYX_MODEL_FAST=deepseek-v4-flash
# One memory file per capability + web cache partitioned by host:
NYX_MEMORY_PER_CAPABILITY=1
# SEC requires a real contact for EDGAR (format: "Name email").
EDGAR_IDENTITY=Your Name you@example.com
# Egress allowlist for live investing (empty = allow all).
NYX_ALLOWED_DOMAINS=sec.gov,www.sec.gov,data.sec.gov,efts.sec.gov,finance.yahoo.com,berkshirehathaway.com,www.berkshirehathaway.com,news.google.com
```

Then:

```powershell
python -m pip install -e ".[investing]"   # edgartools for SEC/XBRL + pypdf
nyx mcp-init                               # register the edgartools MCP server (no Docker)
nyx skills                                 # load the deep skill packs into memory
nyx preflight --probe                      # verify live readiness before going autonomous
nyx run "<your objective>" --keep-going --autonomy autonomous
```

**Model gotcha (already handled):** the current cloud models are *reasoning*
models — they emit chain-of-thought in a separate field and only fill `content`
after thinking, so a too-small `max_tokens` returns empty. NYX's provider detects
this and retries automatically; keep `NYX_MODEL_FAST` on a fast model like
`deepseek-v4-flash`. Without a key NYX runs in deterministic **mock mode** — fully
testable, but deliverable quality comes from the live model. Full steps in the
[go‑live runbook](docs/RUNBOOK.md).

## Status

NYX is a **runnable reference framework** — **179 tests passing**, `ruff` clean,
CI on 3.10–3.12. Functional and tested: the LLM‑routed capability runner, the
three capabilities, the gated dark‑factory pipeline + fan‑out, agentic tool use,
the Darwin‑Gödel evolution archive (genomes adopted back in), three‑layer memory
with consolidation and embedding recall, the long‑document context engine, the
security stack (constitution, injection classifier, SSRF/egress guard,
least‑privilege typed tools, sandbox, audit ledger), and the Ollama Cloud
provider. The **deep-value investing** pipeline is live end-to-end: whole-market
SEC screening (bulk XBRL frames), real prices, full-10-K multi-chunk reads, 13F /
footnotes / 8-K / Form 4 via the edgartools MCP server, news, and the as-of-today
`nyx screen`. Agent "work" is real model calls when a key is present and
deterministic stubs otherwise, so the whole architecture runs offline today.

> **Honest scope.** This is strong defense‑in‑depth and a real autonomy engine,
> not a proof of safety or a guarantee of investment returns — the constitution
> explicitly forbids guaranteeing returns. The deliverable quality tracks the
> model you point it at.

## License

[MIT](LICENSE)
