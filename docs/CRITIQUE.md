# NYX — an honest self-critique and growth roadmap

Written adversarially, on purpose. If NYX is going to be the next big thing it has
to survive a skeptical technical buyer. Here is where it is real, where it is
theater, and where the defensible opportunity actually is.

## The uncomfortable core truth

**NYX is a harness, not a mind.** Its reasoning ceiling is the Ollama model it
calls. It will not out-reason a frontier model like *Mythos* — it *rides on*
models like it. Any claim of "outperforming world-leading models" is only true on
axes those models structurally lack:

- **Persistence** — a chat model is stateless; NYX remembers across months.
- **Grounding** — it reads primary sources (SEC filings) and executes code.
- **Optimization of *your* objective** — a general model isn't trying to maximize
  your CAGR or your promotion; NYX can be pointed at exactly that and evolved.
- **Governance & auditability** — every action is gated and logged.

So the honest positioning is not "smarter than Mythos." It is: **the system that
turns a frontier model into a verifiable, compounding, domain-specialized operator
for one person.** That is a real and large market — but only if the parts below
become real.

## What was theater (and the first one is now fixed)

1. **Gates graded their own homework.** *(Fixed — all five gates now verified.)*
   Gates used to trust claims the agents wrote about themselves. Now
   `factory/verify.py` checks each against reality: `G_TESTS` **executes** the
   code against the tests in the sandbox; `G_SECURITY` **scans** the code for
   secrets/injection/dangerous constructs; `G_SPEC` requires structural
   acceptance‑criteria + non‑goals; `G_DEPLOY` requires a described rollback;
   `G_AUDIT` is derived from the **ledger** (hash chain intact + this run wrote
   entries). Each is a fail‑closed veto over the agent's self‑claim, and each is
   covered by a "lie is blocked" test. (Writing the first one immediately exposed
   a mock coder variant that referenced un‑imported modules and had never
   actually run — the definition of theater.)

2. **Evolution is mostly a keyword game.** The software fitness function is ~70%
   "does the charter contain doctrine words," and the value fitness maps a genome
   to factor weights by counting phrases. So "evolution" largely rediscovers the
   doctrine we already seed. It is *not yet* meaningfully improving capability.
   The mechanism (Darwin-Gödel archive, no-regression admission) is sound; the
   **fitness signal is weak**. Real evolution must score genomes on *executed task
   success* — the SWE-bench harness and the value backtest are the two honest
   signals; everything else should be retired.

3. **"Semantic" memory is lexical.** The embeddings are a character-n-gram hashing
   vectorizer — better than keyword overlap, but it is not semantic. Two passages
   that share meaning but no words won't match. Real semantic recall needs true
   embeddings (the Ollama embed endpoint; the `ProviderEmbedder` seam exists but
   is unused by default).

4. **The software factory never validates the product.** It "ships" artifacts it
   (until now) never ran, never deploys anything real, and has no user/market
   feedback. `deploy`/`operate` are narrative. There is no outer loop connecting
   NYX's output to reality (did the feature work? did anyone pay?).

5. **The agentic loop is shallow.** `run_with_tools` is 3-step ReAct with a regex
   `CALL` protocol, no native function-calling, no error-recovery/retry, no
   sub-goal planning, no verification of tool results. Frontier agent harnesses
   are far deeper.

## Gaps ranked by leverage (what to build next)

1. **Verify every gate, not just tests.** Extend the `verify_artifact` pattern:
   run a real secret/injection scan for `G_SECURITY` (we have the scanners — wire
   them as the *source* of `security_ok`, not the agent's word); derive `audited`
   from the ledger; check `deploy_reversible` structurally. Kill self-reported
   claims entirely. **This is the credibility unlock.**
2. **Make evolution optimize real outcomes.** Default the coder benchmark to the
   executed SWE-bench pass-rate; keep genome-quality only as a small tie-breaker.
   For investing, the live walk-forward backtest is already the right signal —
   turn it on with real data.
3. **Real embeddings for memory.** Wire `ProviderEmbedder` to the Ollama embed
   endpoint when a key is present; keep the hashing embedder as the offline
   fallback. This makes "it remembers what's relevant" true.
4. **Close an outer feedback loop.** For code: run it, and feed runtime/lint/CI
   results back as lessons. For investing: paper-trade the shortlist and record
   realized P&L as memory. Reality, not self-report, must be the teacher.
5. **Deepen the agent loop.** Native tool-calling, tool-error recovery, explicit
   plan/act/verify sub-steps, and a critic pass on tool outputs.
6. **A real evaluation harness.** Contamination-controlled task suites per
   capability with tracked scores over time — so "it keeps getting better" is a
   chart, not a claim.

## Where NYX can genuinely out-perform frontier models

Only where there is a **verifiable objective + private, compounding data + a need
for governance**. Concretely:

- **Deep-value screening** — a frontier chat model won't read 60 filings nightly,
  won't remember last quarter's footnote flags, and isn't optimizing your
  drawdown-adjusted return. NYX, with the live backtest as its fitness function,
  can specialize and compound where a general model stays generic.
- **Evidence-compounding personal campaigns** (EB-1A) — the moat is *sustained,
  contemporaneous* evidence over years; memory + scheduling beats a smart but
  amnesiac assistant.
- **Governed, auditable automation** — regulated or high-stakes work where "show
  the trail and the rule that was enforced" is the product.

The wedge is **narrow and deep, not broad**. NYX loses the "general assistant"
game; it wins the "relentless specialist that improves on your data and proves its
work" game.

## Product / go-to-market realism

The honest gap: **this is a framework, not yet a product.** A solopreneur will not
run a Python CLI on a mini-PC juggling Ollama and EDGAR keys. To be the next big
thing NYX needs (a) a single hosted capability with a real wedge — I'd pick the
**deep-value research agent** because it has a verifiable objective and a
willing-to-pay audience — (b) a one-click experience, and (c) a visible
"it-got-better-this-week" loop (the evolution chart + the ledger as *trust*).
Sell the outcome (a monitored, improving, auditable analyst), not the framework.

## Bottom line

The architecture is genuinely good: modular capabilities, one governed loop,
Darwin-Gödel evolution, three-layer memory, a constitution, and now **executed
verification**. The scaffolding is real. What's thin is the *signal* — fitness,
embeddings, and outcome feedback are proxies today. Convert those three proxies
into measured reality and NYX stops being an impressive demo and becomes a system
that compounds — which is the only way it earns the right to the "next big thing"
claim.
