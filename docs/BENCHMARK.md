# Benchmarking NYX — honestly

The question: *can NYX on Ollama Cloud Pro genuinely do a better job than a
frontier model ("Mythos") and elite PhD humans on all long-running,
goal-oriented tasks?*

Short answer: **No — not "all," and not on raw capability. Yes — on a specific,
valuable slice.** This page shows what was actually measured, what it does and
doesn't prove, and a dimension-by-dimension verdict.

## What was measured (in-repo, deterministic)

These are **mechanism** benchmarks (does the loop work and generalize?), run on
synthetic/held-out data in mock mode. They are **not** capability benchmarks
against Mythos or humans.

| Benchmark | Result | What it shows / doesn't |
| --- | --- | --- |
| Held-out SWE-bench (mock coder) | 0.75 pass | The executed test-gate + eval harness work; the mock coder is constant, so this is **not** a coding-skill measure. |
| Held-out value backtest — doctrine vs none | doctrine **+0.089 / +14.0%** vs none **−0.315 / −6.8%** (universes never trained on) | Evolution/doctrine encoding **generalizes** to unseen data — the *machinery* is real. **Not** evidence of market alpha: the universe is synthetic with a built-in signal; real markets are adversarial/efficient. |
| Self-improvement (held-out) | evolved analyst −0.31 → +0.17 (+0.49) | The evolve→adopt→verify loop lifts held-out score — real *generalization*, on toy data. |
| Engineering | 167 tests, 57 modules, OWASP LLM+Agentic hardened, all 5 gates verified | The system is real and disciplined — a capability *substrate*, not a capability *score*. |

**Honest caveat:** none of the above proves superiority over anyone. To truly
benchmark against Mythos/PhDs you need real suites — SWE-bench Verified,
GPQA-Diamond, point-in-time backtests with transaction costs, real EB-1 outcomes
— with a live frontier-class brain. That is future work and requires the live
setup.

## The brain is the ceiling

NYX is a **harness**; its reasoning ceiling ≈ the model it calls. Ollama Cloud
hosts strong **open-weight** models (Qwen/DeepSeek/GLM/Kimi/gpt-oss/Llama-class).
As of early 2026 these are near-frontier on many tasks but generally **trail the
very top proprietary frontier model** on the hardest reasoning, and are **well
below elite-PhD level** on genuine novel research and judgment. NYX cannot lift
its brain above its model. (Note: the model IDs in the repo config are
illustrative placeholders — set real Ollama model names before drawing
conclusions.)

## Dimension-by-dimension verdict

NYX+Ollama vs a frontier model (Mythos) vs an elite PhD human, on long-running
goal work:

| Dimension | Winner | Why |
| --- | --- | --- |
| Raw reasoning / per-step accuracy | **Mythos** > PhD > NYX | NYX's brain is a notch below frontier. |
| Novel insight / judgment / taste | **PhD** > Mythos > NYX | Scaffolding doesn't create insight. |
| Effective context on huge docs | **≈ tie** (NYX by engineering) | chunk→retrieve→compaction lets a smaller window read a 200k-char 10-K; lossy vs a true 1M-context model. |
| Persistent memory across sessions | **NYX** | Frontier chat is stateless; NYX consolidates durable long-term memory. |
| Retrieval / recall | mixed | a huge-context model holding one doc beats NYX on that doc; NYX scales across *many* docs/months. |
| Tirelessness / throughput / 24-7 | **NYX** | runs unattended, in parallel, forever. |
| Consistency / governance / auditability | **NYX** | verified gates + tamper-evident ledger; humans/raw models don't self-verify. |
| Improvement on a *verifiable* objective | **NYX** | evolves against executed fitness; a frozen model doesn't, a human is slower/costlier. |
| Open-ended / ambiguous goals | **PhD** >> NYX | without a verifiable signal NYX drifts. |
| Cost per unit work | **NYX** | open-weight + no salary. |

## Bottom line

- On **raw capability, novel insight, and open-ended judgment** → Mythos and
  elite PhDs win. NYX does **not** beat them, and "all long-running goals" is a
  category error: many are insight-bound, not effort-bound.
- On the slice that is **verifiable + effort/consistency-bound + memory-heavy**,
  run **tirelessly, cheaply, auditably, and compounding over time** → NYX can
  genuinely beat both a smarter-but-stateless model (which forgets and doesn't
  act) and a human (fatigue, cost, inconsistency). This is a real, valuable slice
  — monitored research, evidence-compounding campaigns, gated delivery — but it
  is a slice, not "everything."

The moat is also the limit: **NYX is strongest exactly where the objective is
measurable.** Give it a verifiable target and time, and it out-executes; ask it
for a genuinely novel thesis, and defer to the PhD.
