# Memory & Continual Learning — how NYX remembers and gets wiser

Your question: *how does the system remember things, and how do learnings from
evolution and dark‑factory execution accumulate?*

NYX learns on **three distinct memory substrates**, each answering a different
question. Together they make the factory compound knowledge over time — on a
single mini‑PC, fully offline, with no vector database or retraining.

| Layer | Question it answers | Where it lives | Mutability |
| --- | --- | --- | --- |
| **Episodic** | *What happened?* | [Audit ledger](../nyx/observability/ledger.py) | append‑only, hash‑chained (immutable) |
| **Procedural** | *How do we get better at the job?* | [Evolution archive](../nyx/evolution/archive.py) | grows; best genomes retained |
| **Semantic** | *What did we learn that we should reuse?* | [Memory store](../nyx/memory.py) | distilled, reinforced, decays |

## 1. Episodic memory — the audit ledger

Every consequential action (each agent artifact, gate decision, deploy, evolve,
adopt) is appended to a **hash‑chained, tamper‑evident ledger** with actor,
action, rationale, and the constitutional verdict. This is perfect, ordered
recall of *events* — the factory's black box. It is never edited; breaking the
chain is detectable (`AuditLedger.verify()`).

## 2. Procedural memory — the evolution archive

The Darwin‑Gödel [archive](EVOLUTION.md) stores improved **agent genomes**
(prompts, tools, params) — admitted only when they beat their ancestor on a
benchmark. This is "muscle memory": the factory literally becomes a better
engineer, and the skill is banked durably and **adopted back into the factory**
on the next cycle. Gains persist across missions because the archive is on disk.

## 3. Semantic memory — distilled lessons (new)

This is the layer most people mean by "memory". After every run, a **reflection**
step distills durable, reusable *lessons* from the outcome:

- a **blocked gate** → a guardrail lesson (*"for work like X, satisfy G_SECURITY
  early: …"*),
- a **security finding** → a risk lesson (*"watch for: injection from ticket"*),
- a **clean ship** → a reinforced pattern (*"this gated pipeline shipped X
  cleanly"*).

Lessons are stored in a JSONL [`MemoryStore`](../nyx/memory.py). On the next
task, the factory **recalls** the most relevant lessons (keyword‑overlap ×
reinforcement weight — no embeddings needed) and **injects them into every
agent's system prompt** under `# LEARNED LESSONS`. So the agents *apply* what was
learned without any retraining.

```
execute ─▶ REFLECT (distill lessons) ─▶ REMEMBER ─▶ RECALL on next task ─▶ better execution
```

Lessons that recur are **reinforced** (weight rises, deduped); stale ones lose
weight over time. This keeps memory relevant rather than ever‑growing noise.

## How the three reinforce each other

```
            ┌──────────────────── a single mission ─────────────────────┐
 objective ─┤  build  →  ledger (episodic: what happened)                │
            │     │                                                      │
            │     ├─▶ reflect → memory (semantic: lessons) ──┐           │
            │     │                                          ▼           │
            │     └─▶ evolve → archive (procedural: skills)  recall next │
            │                      │                         build       │
            │                      └─ adopt better agents ───┘           │
            └───────────────────────────────────────────────────────────┘
```

- **Episodic** is the raw truth the other two are derived from.
- **Semantic** turns episodes into *advice* the agents follow immediately.
- **Procedural** turns repeated success into *better agents* permanently.

A new objective therefore benefits from: the lessons of every prior run
(semantic), the best agents evolution has found (procedural), and a complete
audit trail of how it all happened (episodic).

## Operating it

```bash
nyx run "Launch a billing platform"     # builds, reflects, evolves, remembers
nyx memory                              # list learned lessons (by weight)
nyx memory --recall "invoice exports"   # what would be applied to a new task
nyx ledger --tail 30                    # the episodic record (incl. recall/reflect events)
nyx evolve --suite swebench -g 10       # grow procedural memory against real tests
```

Back up `.nyx/` — it holds all three memories (ledger, archive, lessons). That
directory *is* your company's accumulated experience.
