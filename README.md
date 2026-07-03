# NYX — The Autonomous Dark Factory

> A constitutional, self‑evolving, multi‑agent software factory that explores,
> designs, builds, ships, and operates real products with **zero physical
> employees** — running on an **Ollama Cloud** brain from a single
> **Windows 11 mini‑PC**.

NYX (the Greek goddess of night — the *lights‑out* factory) is an agentic
operating system for the **solopreneur of the autonomous era**. One human sets
the intent. A swarm of specialized AI agents does the rest: feature
exploration, product design, coding, review, testing, deployment, and 24/7
operational excellence.

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
| **Autonomous mission loop** | Objective → plan → build → evolve → adopt → repeat | [`nyx/mission.py`](nyx/mission.py) |
| **Dark Factory** | End‑to‑end autonomous SDLC pipeline | [`nyx/factory`](nyx/factory) |
| **Fan‑Out Factory** | Many agents work the same stage in parallel; the best result wins | [`nyx/factory/fanout.py`](nyx/factory/fanout.py) |
| **Constitutional AI** | Principles enforced on every model call | [`nyx/constitution.py`](nyx/constitution.py) |
| **Self‑Evolving Agents** | Darwin‑Gödel archive of improving agents | [`nyx/evolution`](nyx/evolution) |
| **Memory & continual learning** | Episodic + procedural + semantic memory; reflect → remember → recall → consolidate | [`nyx/memory.py`](nyx/memory.py) |
| **Pluggable capabilities** | Drop‑in goal handlers on one autonomous runner (e.g. value investing) | [`nyx/capabilities`](nyx/capabilities) |
| **Real benchmarks** | SWE‑bench‑style code execution + point‑in‑time value backtest | [`nyx/evolution/benchmarks.py`](nyx/evolution/benchmarks.py), [`nyx/domains/investing`](nyx/domains/investing) |
| **Secure AI** | Prompt‑injection guards, secret hygiene, sandboxing | [`nyx/security`](nyx/security) |
| **Operational Excellence** | Audit ledger, metrics, SRE agent | [`nyx/observability`](nyx/observability) |
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
[mission controller](nyx/mission.py) closes the loop:

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
- [Memory & learning](docs/MEMORY.md) — how the factory remembers and gets wiser
- [Context management](docs/CONTEXT.md) — reading full 10-Ks without overflow
- [Tools, MCP & web access](docs/TOOLS.md) — equipping NYX with EDGAR/MCP/scraping
- [Windows 11 deployment](docs/DEPLOYMENT_WINDOWS11.md)

## Status

NYX is a **reference implementation and framework**. The autonomous mission
loop, orchestration, constitution engine, evolution archive (with genomes
adopted back into the factory), guardrails, audit ledger, and Ollama Cloud
provider are all functional and covered by tests. Agent "work" is performed by
real model calls when a key is present and by deterministic stubs otherwise, so
the architecture is fully runnable and testable today.

## License

[MIT](LICENSE)
