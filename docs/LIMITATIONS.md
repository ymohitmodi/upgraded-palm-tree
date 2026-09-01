# Designing around LLM & harness limitations

Every LLM system inherits hard limitations. Pretending otherwise is how you ship
something that looks impressive and fails in production. NYX names each limitation
and designs a concrete control around it — that discipline is what turns a demo
into a force multiplier you can actually trust with unattended work.

| Limitation (LLM/harness) | Why it bites | How NYX designs around it |
| --- | --- | --- |
| **Hallucination / confident wrong answers** | Models assert false facts fluently | Investing gates require **sourced numbers** and forbid guarantees; the test gate is **execution-verified** (not self-graded); fan-out + a judge; "cite or mark uncertain" doctrine in skills |
| **Self-grading (grades own homework)** | An agent claiming `TESTS_PASS=true` proves nothing | `factory/verify.py` **runs** the code against the tests in the sandbox and sets the claim from reality; lying is blocked |
| **Finite context window** | A 10-K overflows any window; truncation loses footnotes | `context.py` **refine-fold** (bounded running synthesis over all chunks) + **embedding retrieval** for details — reads everything, holds little |
| **Prompt injection** | Fetched content can hijack the agent | Untrusted content delimited as data; heuristic + **LLM injection classifier**; constitution A3/A5 |
| **Memory poisoning** | Malicious text can become "learned truth" | External memories are `trusted=False`, screened, and **excluded from doctrine**; recall down-ranks them |
| **Statelessness / amnesia** | Chat models forget between sessions | Three-layer memory + **consolidation** into durable long-term principles on disk |
| **Non-determinism** | Same prompt → different output | Temperature control per genome; **gates** validate outputs; deterministic mock for tests/CI |
| **Cost / runaway loops** | Agents can loop and burn spend | One **shared call/spend budget**; ReAct step caps; rate limits; bounded crawl/chunks |
| **Weak self-improvement signal** | "Evolution" can optimize noise | Darwin-Gödel **no-regression** admission; benchmarks that **execute** (SWE-bench harness, value backtest) — with the honest caveat that some fitness terms are still proxies (see [CRITIQUE](CRITIQUE.md)) |
| **Tool errors / partial failures** | One bad tool call shouldn't sink the run | Tools never raise into the loop (structured `ToolResult`); crawl survives per-URL failures; MCP **timeout**; graceful degradation everywhere |
| **Over-agency / unsafe actions** | Autonomy can do irreversible harm | **Least-privilege** tools per capability; deploy gated to autonomy + human approval; SSRF/egress guard; hash-chained **audit ledger** |
| **Model identity/version drift** | The brain changes under you | Provider abstraction + config; deterministic fallbacks; everything re-verified by gates, not assumed |

## The force-multiplier thesis

A frontier model answers your question once. NYX is designed to **do the recurring
work and prove it** — within these limitations, not in denial of them:

- **It compounds.** Memory + consolidation mean it gets more useful on *your*
  data every week, where a stateless chat resets to zero.
- **It shows its work.** The audit ledger and verified gates mean you can trust —
  and defend — what it did unattended.
- **It stays on-budget and in-bounds.** You can leave it running because agency is
  capped, egress is guarded, and spend has a ceiling.
- **It specializes.** Pointed at a verifiable objective (a backtest, a passing
  test suite, an EB-1 criteria checklist) it optimizes *that*, which a general
  model never does.

Use a chat model to think; use NYX to execute, remember, verify, and compound —
so one person operates like a team. That is the multiplier, and it only holds
because the limitations above are engineered around, not wished away.
