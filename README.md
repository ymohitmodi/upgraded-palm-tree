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
| **Dark Factory** | End‑to‑end autonomous SDLC pipeline | [`nyx/factory`](nyx/factory) |
| **Fan‑Out Factory** | Many agents work the same stage in parallel; the best result wins | [`nyx/factory/fanout.py`](nyx/factory/fanout.py) |
| **Constitutional AI** | Principles enforced on every model call | [`nyx/constitution.py`](nyx/constitution.py) |
| **Self‑Evolving Agents** | Darwin‑Gödel archive of improving agents | [`nyx/evolution`](nyx/evolution) |
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

# 4. Watch the constitutional, audited pipeline run
nyx status
nyx ledger --tail 20

# 5. Let the agents evolve themselves against a benchmark
nyx evolve --generations 5
```

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
- [Evolution](docs/EVOLUTION.md) — how agents improve themselves
- [Windows 11 deployment](docs/DEPLOYMENT_WINDOWS11.md)

## Status

NYX is a **reference implementation and framework**. The orchestration,
constitution engine, evolution archive, guardrails, and Ollama Cloud provider
are functional. Agent "work" is performed by real model calls when a key is
present and by deterministic stubs otherwise, so the architecture is fully
runnable and testable today.

## License

[MIT](LICENSE)
