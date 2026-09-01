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

2. **Evolution is mostly a keyword game.** *(Fixed for the coder role.)* The
   coder fitness is now the **executed** SWE-bench pass-rate (0.85 weight) with a
   small genome tiebreaker — genomes are scored on code that actually runs, not on
   doctrine words. The value fitness uses the executed backtest. Remaining: the
   value factor-weight mapping is still a proxy when offline (LLM-derived live),
   and non-executable roles (reviewer/planner) still fall back to charter quality
   because they have no runnable artifact.

3. **"Semantic" memory was lexical.** *(Fixed.)* Real embeddings are wired: a live
   provider supplies semantic vectors via `ProviderEmbedder` (Ollama
   `/v1/embeddings`), selected automatically by `embedder_for`; the hashing
   embedder remains the deterministic offline fallback.

4. **The factory didn't validate its work → now it does, and feeds it back.**
   *(Substantially fixed.)* All five gates are execution/scan/ledger-verified, and
   realized outcomes now flow back as a **track record** (`kind="track-record"`,
   trusted): the value backtest's realized risk-adjusted return per decision, and
   a "shipped through execution-verified gates" record for software (`nyx track`).
   Still missing: a *market* signal (did anyone pay?) and live paper-trading over
   real time rather than the backtest as ground truth.

5. **The agentic loop was shallow.** *(Deepened.)* `run_with_tools` now supports
   **native function-calling** (OpenAI-style `tools`/`tool_calls`, typed from
   ArgSpec, allowlist-filtered), **multiple tool calls per turn**, **bounded
   error recovery** (failures are fed back as `[error]` observations with a hint;
   after repeated failures it answers from what it has), a **critic pass on tool
   outputs** (empty/off-topic/low-signal results are flagged `[low-signal …]` so
   the agent verifies or re-sources instead of building on junk), and a sub-goal
   scratchpad — with the text `CALL` protocol retained as a fallback. Remaining
   depth: longer-horizon planning and an optional LLM-backed critic.

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
Darwin-Gödel evolution, three-layer memory, a constitution, executed
verification, and now — after closing the three "signal" gaps — **executed
fitness, real embeddings, and an outer feedback loop** (a track record of
realized outcomes). The **standing eval harness now exists** (`nyx eval`): held-out,
contamination-controlled score per capability, tracked over time — and it already
shows the evolved analyst beating its seed on universes it never trained on
(−0.31 → +0.17). The remaining honest gaps are narrower still: a *market/payment*
signal, live paper-trading over real time, and a deeper agent loop
(native function-calling, error recovery, sub-goal planning). Those are product
and longitudinal-data problems now, not architectural ones — which is exactly the
position from which a system earns the right to compound.
