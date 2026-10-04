# Context management — read everything, never overflow

A single SEC 10-K can exceed 200,000 characters — far more than any context
window. Truncating loses the footnotes that decide the investment. NYX manages
context the way a careful analyst does: **read all of it, in passes, keeping a
running understanding, and remember where every detail lives.**

Implemented in [`nyx/context.py`](../nyx/context.py) (`LongDocReader`).

## Two complementary mechanisms

### 1. Hierarchical refine-fold (whole-document understanding, bounded)

The document is split on natural boundaries into token-bounded chunks, then
folded left-to-right into a **running synthesis**:

```
synthesis₀ = ""
for each chunk:   synthesisᵢ = distill(synthesisᵢ₋₁, chunkᵢ, budget)
```

The model never sees more than *(bounded synthesis + one chunk)* at a time, so
it **cannot overflow** — yet every chunk is read and its salient content carried
forward. The output is a bounded, faithful understanding of the *entire*
document. With a live brain `distill` is an LLM call that preserves figures,
risks, and footnote details; offline it is a deterministic extractive
summarizer, so the pipeline is fully testable.

### 2. Embedding-indexed retrieval (full detail on demand)

Every chunk is embedded (the hashing embedder offline, or live semantic
embeddings) and kept. A specific question —

> "what are the off-balance-sheet lease obligations?"

— retrieves the exact relevant chunks by cosine similarity and answers from
them, **without ever loading the whole document**. Verified: a footnote buried
in item 83 of a 210k-char filing is recovered by query even though the running
synthesis is only ~2.5k chars.

## Why nothing is lost, yet context stays small

| | Guarantee |
| --- | --- |
| **Reads everything** | every chunk is processed (fold) *and* indexed (retrieval) — no truncation |
| **Doesn't lose context** | the refine-fold carries a running synthesis across all chunks; all chunks remain retrievable by meaning |
| **Manages wisely** | the LLM sees only *(summary + one chunk)* when reading, or *top-k chunks* when answering — always within budget |

## Using it

```bash
nyx read https://www.sec.gov/.../aapl-10k.htm --query "lease and pension footnotes"
nyx read ./annual_report.txt
```

As a tool (the analyst calls it automatically): `read_url(url, query="")` returns
the bounded whole-document synthesis, plus the most relevant sections when a
query is given. It is an **external** tool, so its output is injection-classified
and secret-scanned before entering agent context (see [SECURITY](SECURITY.md)).

## Goal-driven context assembly (the broker)

Reading a document is only half of context management; the other half is deciding
**what internal knowledge a goal needs** and injecting *only* that. The
[`ContextBroker`](../nyx/context_broker.py) sits in front of every agent run and
solves the two failure modes:

- **Missing context (discovery).** A single query misses knowledge the goal
  *implies*. The broker probes the goal **and its sub-phrases** (split on
  connectives), keeps each memory's best match across probes, and so surfaces the
  lessons/skills/track-record that actually bear on the goal — e.g. a "billing
  dashboard **and** retention" goal pulls both the billing and the churn lessons,
  which one query would miss.
- **Context pollution (hygiene).** Dumping many tiny, weak, or duplicate snippets
  makes the model *worse*. The broker applies an **absolute + relative relevance
  floor** (drop anything far below the top match — scale-invariant, so it works
  even with weak vectors), **de-duplicates**, **drops trivially short low-signal
  items**, and **caps the total by a character budget**. Only the high-signal,
  non-redundant minimum reaches the agent.

The runner and factory both assemble context through the broker before acting,
and log a `context_assembled` ledger entry (how many kept vs dropped). Net effect:
NYX *discovers* the context a goal requires and stays **lean** — it never buries
the model in short, off-topic noise.

The same machinery underlies the factory's inter-stage **working-memory
compaction** (bounded context between pipeline stages) and the memory store's
consolidation — one coherent story: discover and inject the useful minimum, bound
what the model holds at once, and keep everything else recoverable from memory.
