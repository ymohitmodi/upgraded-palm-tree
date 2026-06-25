# Capabilities — pluggable, goal-specific autonomy

NYX separates **what to pursue** (a *Capability*) from **how to pursue it
autonomously** (the *CapabilityRunner*). Give it an objective; it routes to the
capability that handles that goal and runs the same continual-learning loop:

```
plan → refresh knowledge → execute (decide) → reflect → recall →
       evolve (vs the capability's benchmark) → consolidate → repeat
```

— all on shared memory, evolution, budget, and audit machinery. The software
dark-factory and the value investor are both just capabilities.

```bash
nyx capabilities                       # list what NYX can pursue
nyx capabilities "undervalued stocks"  # show which capability handles an objective
nyx run "<objective>"                  # auto-routes to the matching capability
```

## Anatomy of a Capability

Implement [`nyx/capabilities/base.py:Capability`](../nyx/capabilities/base.py):

| Hook | Purpose |
| --- | --- |
| `matches(objective)` | does this capability handle the objective? |
| `evolve_role()` / `directives()` | which agent genome to evolve, and its doctrine pool |
| `benchmark(ctx)` | the fitness signal for evolution |
| `constitution(base)` | add domain gates (values) |
| `seed_memory(memory)` | seed durable doctrine into long-term memory once |
| `refresh_knowledge(ctx)` | keep reading the world (filings, reports) |
| `plan(objective, ctx)` | decompose into a backlog of cycle tasks |
| `execute(task, ctx)` | do the work and make a decision |

Register it (`nyx/capabilities/registry.py`) and it's selectable — nothing else
changes. The runner gives it memory, recall, evolution, consolidation, budget,
and a tamper-evident audit trail for free.

## Built-in: `value-investing`

[`nyx/domains/investing/capability.py`](../nyx/domains/investing/capability.py)
turns the deep-value objective into action:

- **Role/doctrine**: evolves the `analyst` genome with `INVESTING_DIRECTIVES`.
- **Benchmark**: the point-in-time `ValueBenchmark` — **real EDGAR + price data
  when reachable** (`try_build_universe`), synthetic walk-forward otherwise.
- **Governance**: the investing constitution (no guaranteed returns, no
  un-sourced numbers, margin-of-safety required).
- **Memory**: seeds the Buffett doctrine, then **keeps reading** Berkshire annual
  letters + SEC filings into long-term memory every cycle (`refresh_knowledge`).
- **Decisions**: each cycle it ranks the universe and emits a gated, Buffett-style
  shortlist memo; as evolution improves the analyst, the decisions improve.

```bash
nyx run "Find deep-value undervalued public companies; learn from Buffett; \
keep reading SEC filings and Berkshire reports" --autonomy autonomous --max-cycles 8
```

Offline demo: decisions climb from a negative score (no doctrine) to a positive
risk-adjusted score once the doctrine is seeded/evolved, with 15 long-term
lessons and an intact ledger.

### Going live with real data

The data layer ([`data.py`](../nyx/domains/investing/data.py)) is **guarded**: if
`edgartools` is missing or the network is blocked, it raises `DataUnavailable`
and the benchmark falls back to the synthetic universe — the loop never stalls.
To run on real data:

1. `pip install -e ".[investing]"` and set `EDGAR_IDENTITY`.
2. Allow the hosts (see [docs/TOOLS.md](TOOLS.md)): `www.sec.gov`, `data.sec.gov`,
   `stooq.com`, `www.berkshirehathaway.com`. (Claude Code on the web denies these
   by default; a mini-PC deployment has open internet.)
3. `nyx run "<objective>"` — same command, now reading real filings and prices.

## Adding your own capability

Drop a class implementing `Capability` (e.g. legal research, biotech screening),
register it, and give NYX the matching objective. It inherits the full stack:
constitutional gates, three-layer memory + consolidation, Darwin-Gödel evolution,
context compaction, budget, and audit — you only write the goal-specific parts.
