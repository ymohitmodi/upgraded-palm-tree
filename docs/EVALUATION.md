# Standing evaluation — making "it got better" visible

Claims that a system "keeps improving" are worthless without a measurement that
is (a) **held out** from training and (b) **tracked over time**. NYX's eval
harness ([`nyx/evaluation.py`](../nyx/evaluation.py)) provides both, so
compounding is a chart you can point at — the trust artifact behind the whole
thesis.

```bash
nyx eval              # run held-out evals, record the score, show delta vs last
nyx eval --history    # show the score trend (sparkline) over all past runs
```

## Contamination control

Evolution trains against one set of tasks; the eval scores against a **disjoint**
set, so a genome can't win by memorizing the test:

- **software** → `heldout_swebench_suite()` (task ids `ho_*`, disjoint from the
  training suite) executed in the sandbox → pass fraction.
- **value-investing** → `heldout_universes()` (seeds `101/103/107`, disjoint from
  the training seeds `7/11/13`) → risk-adjusted return of the analyst's picks.
- **advisor** → not objectively scorable yet (no ground-truth signal), so it
  reports no score rather than a fake one.

A test asserts the held-out ids/seeds are disjoint from training.

## What it records

Each run appends a timestamped `EvalRecord` (capability, score, detail) to
`.nyx/evals.jsonl`. `nyx eval` prints the current score and the **delta since the
last run**; `nyx eval --history` renders the trend. Because the suites are held
out, a rising line is genuine generalization, not overfitting.

## Proof it works

Evolving the analyst, then re-running the held-out eval:

```
value-investing  -0.3148   (seed analyst)
value-investing  +0.1724   (+0.4872 vs last)   (evolved analyst)
trend:  ▁█   [-0.315  0.172]
```

The evolved genome scores materially higher on universes it **never trained on** —
the evolution → adoption → verified-improvement loop is real and measurable, not
asserted. (In deterministic mock mode the software coder is constant at 0.75, so
its line is flat — honestly reported, not massaged.)

## Operating it

Run `nyx eval` on a schedule (cron / the mini-PC) to build the longitudinal
record; `nyx eval --history` is your "did it get better this week?" answer.
Pair it with `nyx track` (realized-outcome track record) and `nyx ledger` (the
audit trail) for the full evidence picture.
