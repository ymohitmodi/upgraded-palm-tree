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

The same machinery underlies the factory's inter-stage **working-memory
compaction** (bounded context between pipeline stages) and the memory store's
consolidation — one coherent story: bound what the model holds at once, and keep
everything else recoverable from memory.
