# Architecture

NYX is a layered, constitutional, multi‑agent system. Each layer has one job and
a clean seam to the next.

```
┌──────────────────────────────────────────────────────────────────────────┐
│  OPERATOR (human)            nyx CLI  ── intent, gates, taste              │
├──────────────────────────────────────────────────────────────────────────┤
│  FACTORY ORCHESTRATOR        nyx/factory/orchestrator.py                   │
│   Explore → Design → Build → Review → Test → Ship → Operate               │
│   each stage runs a FAN-OUT swarm (nyx/factory/fanout.py)                  │
├──────────────────────────────────────────────────────────────────────────┤
│  AGENTS                      nyx/agents/*  (role-specialized)              │
│   Explorer · Architect · Coder · Reviewer · Tester · Deployer ·           │
│   Operator · Security                                                      │
├──────────────────────────────────────────────────────────────────────────┤
│  GOVERNANCE                  constitution engine + security guardrails     │
│   nyx/constitution.py · nyx/security/*                                     │
├──────────────────────────────────────────────────────────────────────────┤
│  EVOLUTION                   nyx/evolution/*  (Darwin-Gödel archive)       │
├──────────────────────────────────────────────────────────────────────────┤
│  OBSERVABILITY               nyx/observability/*  (audit ledger, metrics)  │
├──────────────────────────────────────────────────────────────────────────┤
│  PROVIDER (the brain)        nyx/providers/ollama_cloud.py → Ollama Cloud  │
└──────────────────────────────────────────────────────────────────────────┘
```

## The pipeline (Dark Factory SDLC)

Each stage consumes the previous artifact and is guarded by a constitutional
**gate**. A stage cannot complete until its gate passes.

| Stage | Agent(s) | Produces | Gate |
| --- | --- | --- | --- |
| **Explore** | Explorer | Opportunity brief + framed problem | — |
| **Design** | Architect | Spec (acceptance criteria, non‑goals), system design | `G_SPEC` |
| **Build** | Coder (fan‑out) | Implementation candidates | — |
| **Review** | Reviewer + Security | Selected candidate + findings | `G_SECURITY` |
| **Test** | Tester | Test suite + results | `G_TESTS` |
| **Ship** | Deployer | Release plan + gated deploy | `G_DEPLOY` |
| **Operate** | Operator | Health, metrics, incident handling | `G_AUDIT` |

## The Fan‑Out Factory pattern

The "fan factory" idea: for a given stage, **N agents attempt the task in
parallel** with diversified prompts/temperatures/models. A judge (the Reviewer,
itself constitutional) scores the candidates and the **best result wins**. This
trades cheap parallel compute for quality and is the core of how a solo operator
gets team‑scale output.

```
            ┌── Coder#1 (temp 0.2, model A) ─┐
  spec ─────┼── Coder#2 (temp 0.6, model A) ─┼── judge ── best candidate
            └── Coder#3 (temp 0.4, model B) ─┘
```

See [`nyx/factory/fanout.py`](../nyx/factory/fanout.py).

## Governance plane

Two cross‑cutting systems wrap every agent call:

- **Constitution engine** ([`nyx/constitution.py`](../nyx/constitution.py)) —
  injects relevant principles into each agent's system prompt and validates
  outputs against gates + the forbidden list. Fail‑closed by default.
- **Security guardrails** ([`nyx/security`](../nyx/security)) — scrubs secrets,
  neutralizes prompt‑injection in untrusted inputs, and sandboxes any code
  execution.

## Evolution plane

The [evolution engine](EVOLUTION.md) treats each agent's *configuration*
(prompt, tools, params) as a genome. It mutates genomes, evaluates them on a
benchmark, and keeps a [Darwin‑Gödel](https://arxiv.org/abs/2505.22954) archive
of every variant that beat its ancestor — open‑ended, path‑diversified
self‑improvement.

## Observability plane

Every consequential action appends to an **append‑only audit ledger**
([`nyx/observability/ledger.py`](../nyx/observability/ledger.py)) with actor,
action, rationale, constitutional decision, and a hash chain so tampering is
detectable. Metrics track throughput, cost, gate pass‑rates, and evolution
gains.

## The brain: Ollama Cloud

All cognition routes through a single provider abstraction
([`nyx/providers/base.py`](../nyx/providers/base.py)). The default implementation
talks to [Ollama Cloud](https://docs.ollama.com/cloud) over its OpenAI‑compatible
endpoint. Models are addressed by role (architect/coder/reviewer/fast) so you can
re‑route the whole factory to bigger or cheaper models from one config file.
With no key configured, a deterministic **MockProvider** stands in so the entire
architecture is runnable and testable offline.

## Data flow summary

```
intent ─▶ Explorer ─▶ Architect ─▶ [Coder×N → judge] ─▶ Reviewer+Security
        ─▶ Tester ─▶ Deployer ─▶ Operator
   every step: constitution-checked, audited, and feeding the evolution archive
```
