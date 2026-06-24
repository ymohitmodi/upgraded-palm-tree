# Evolution — Self‑Improving Agents

NYX's agents are not static. The factory keeps a
[Darwin‑Gödel Machine](https://arxiv.org/abs/2505.22954) style **archive** of
agent variants and improves them open‑endedly: a mutated agent is admitted to
the archive **only if it empirically beats its ancestor** on a benchmark. This
is the learning‑from‑evolution paradigm — *select an entity from the archive,
modify it, keep it if it is interestingly better*
([Survey of Self‑Evolving Agents](https://arxiv.org/pdf/2507.21046)).

## The genome

An agent's evolvable configuration:

```
Genome = {
  system_prompt:  str     # how the agent thinks
  tools:          [str]   # what it can do
  params:         {temperature, top_p, max_tokens, fanout, ...}
  model_role:     str     # which brain it routes to
}
```

## The loop

```
            ┌─────────────────────────────────────────────┐
            │  ARCHIVE (tree of every admitted genome)     │
            └───────────────┬─────────────────────────────┘
                            │ 1. SELECT a parent (favor high-score + novelty)
                            ▼
                      2. MUTATE the genome (prompt/tool/param edit)
                            │
                            ▼
                   3. EVALUATE on the benchmark suite
                            │
                            ▼
        4. ADMIT iff score > parent_score + threshold (NYX_EVOLUTION_THRESHOLD)
                            │
                            ▼
                   5. record lineage + gain in the ledger
```

- **Open‑ended & path‑diversified.** Because the *whole archive* is kept (not
  just the current best), evolution can revisit and branch from older genomes,
  escaping local optima — the key DGM insight.
- **Empirical, not vibes.** Admission is gated by measured benchmark score, so
  the factory's engineering skill provably compounds.
- **Constitution‑bounded.** Mutations that would violate the Constitution
  (e.g. removing audit, weakening a gate) are rejected before evaluation. The
  agents may evolve their *competence*, never away from their *values*.

## Benchmarks

The evaluator scores genomes on a configurable suite. The reference suite scores
candidate code on: spec adherence, tests passing, constitutional cleanliness,
and cost. You can point it at SWE‑bench‑style tasks or your own product KPIs.

## Constitution amendments

The same engine can propose **amendments to the Constitution itself** — but
`Constitution.validate_amendment()` enforces a *ratchet*: amendments may only
**add** principles or **tighten** existing ones. An amendment that removes or
weakens any `immutable: true` core principle is rejected. The factory's values
can only get safer over time.

## Why this matters for a solopreneur

You don't hire senior engineers; your agents *become* senior engineers. Every
evolution cycle banks durable capability into the archive — capability that runs
on the same mini‑PC for the same monthly cost. The company's skill curve bends
upward without headcount.
