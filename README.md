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

## Quick start

```bash
# 1. Install (editable)
python -m pip install -e .

# 2. Configure (copy and edit). Works in MOCK mode with no key at all.
cp .env.example .env

# 3. Run a full dark-factory build of a feature, end to end
nyx build "Add a usage-based billing dashboard with Stripe metering"

# 4. Or hand NYX an OBJECTIVE and let it run autonomously:
#    plan -> build each feature -> evolve its agents -> adopt the winners -> repeat
nyx run "Launch a SaaS analytics product" --autonomy autonomous --keep-going

# 5. Watch the constitutional, audited pipeline run
nyx status
nyx ledger --tail 20

# 6. Let the agents evolve themselves against a benchmark
nyx evolve --generations 5
```

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
- [Limitations by design](docs/LIMITATIONS.md) — LLM/harness limits and the controls around them
- [Security model](docs/SECURITY.md) — OWASP LLM Top 10 + Agentic threats (`nyx security-audit`)
- [Tools, MCP & web access](docs/TOOLS.md) — equipping NYX with EDGAR/MCP/scraping
- [Windows 11 deployment](docs/DEPLOYMENT_WINDOWS11.md)

## Going live

```bash
pip install -e ".[investing]"          # + edgartools for SEC/XBRL
export OLLAMA_API_KEY=...               # your Ollama Cloud (pro) key → the brain
export EDGAR_IDENTITY="Name email"      # SEC requires it
nyx mcp-init                            # register the SEC EDGAR MCP server
nyx skills                              # load the deep skill packs into memory
nyx run "<your objective>" --keep-going --autonomy autonomous
```

Allow `sec.gov` / `berkshirehathaway.com` / `stooq.com` in your network policy
(or run on a mini‑PC with open internet). Without a key it runs in deterministic
**mock mode** — fully testable, but the deliverable quality comes from the live
model.

## Status

NYX is a **runnable reference framework** — **102 tests passing**, `ruff` clean,
CI on 3.10–3.12. Functional and tested: the LLM‑routed capability runner, the
three capabilities, the gated dark‑factory pipeline + fan‑out, agentic tool use,
the Darwin‑Gödel evolution archive (genomes adopted back in), three‑layer memory
with consolidation and embedding recall, the long‑document context engine, the
security stack (constitution, injection classifier, SSRF/egress guard,
least‑privilege typed tools, sandbox, audit ledger), and the Ollama Cloud
provider. Agent "work" is real model calls when a key is present and
deterministic stubs otherwise, so the whole architecture runs offline today.

> **Honest scope.** This is strong defense‑in‑depth and a real autonomy engine,
> not a proof of safety or a guarantee of investment returns — the constitution
> explicitly forbids guaranteeing returns. The deliverable quality tracks the
> model you point it at.

## License

[MIT](LICENSE)
