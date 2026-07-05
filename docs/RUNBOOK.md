# Go-live runbook — taking a capability live

NYX runs fully in deterministic **mock mode** with zero setup. This runbook takes
one capability *live* (real model + real data) and stands up the evidence loop.
Run **`nyx preflight`** at each step — it checks the live dependencies and tells
you the exact fix for anything missing.

## 0. Install

```bash
git clone <repo> && cd nyx
python -m pip install -e ".[investing]"     # core + edgartools + requests
nyx doctor                                  # framework loads?  should be healthy ✓
```

## 1. Connect the brain (Ollama Cloud)

```bash
export OLLAMA_API_KEY="<your Ollama Cloud pro key>"
export NYX_CONSTITUTION_MODE=block          # fail-closed gates (recommended)
export NYX_MAX_CALLS=400                     # spend budget per run
nyx preflight --probe                        # verifies the key actually responds
```

`--probe` sends a 1-token request; a `✓ brain-probe` means the model is live.
Without a key everything still runs, but on stub outputs — the deliverable
quality comes from the real model.

## 2a. Go live: value-investing

```bash
export EDGAR_IDENTITY="Your Name your@email.com"        # SEC requires a real contact
export NYX_ALLOWED_DOMAINS="sec.gov,data.sec.gov,efts.sec.gov,stooq.com,berkshirehathaway.com"
nyx mcp-init                                             # register sec-edgar-mcp (needs Docker)
nyx skills                                               # load the deep skill packs into memory
nyx preflight --capability value-investing --probe      # edgar identity + edgartools + reachability
nyx universe                                             # should read "EDGAR live walk-forward"
```

Then run it, and stand up the evidence loop:

```bash
nyx run "Find deep-value public companies for a high risk-adjusted return; \
learn from Buffett; keep reading SEC filings and Berkshire reports" \
  --keep-going --autonomy autonomous
nyx eval        # held-out score (run on a schedule to build the trend)
nyx track       # realized-outcome track record
nyx ledger      # the tamper-evident audit trail
```

## 2b. Go live: software

```bash
nyx preflight --capability software --probe
nyx run "Build and ship <your product increment>" --autonomy supervised
```

Start at `--autonomy supervised` (human approves deploys) until you trust it,
then move to `autonomous`. Every gate is verified against reality (tests
executed, code scanned), so "shipped" means it passed real checks.

## 2c. Go live: advisor (career / EB-1)

```bash
nyx preflight --probe
nyx run "Grow my senior SDE career and get EB-1 publications ready" \
  --autonomy autonomous --keep-going
```

## 3. Run it unattended, safely

- **Autonomy ladder:** `assisted` (approve each) → `supervised` (approve deploys)
  → `autonomous` (within policy). Move up only as trust grows.
- **Security posture:** `nyx security-audit` maps your config to the OWASP LLM
  Top 10 + Agentic threats. Keep `constitution_mode=block`, set an
  `allowed_domains` allowlist, and keep keys in the environment (never in
  prompts/repo). See [SECURITY](SECURITY.md).
- **Schedule it:** put `nyx run … --keep-going` and a periodic `nyx eval` on cron
  (or the mini-PC). The eval history is your "did it get better this week?"
  answer; the ledger is your "what exactly did it do?" answer.
- **Back up `.nyx/`** — it holds memory, the evolution archive, the ledger, and
  the eval history: your accumulated, compounding experience.

## 4. Readiness reference

`nyx preflight` statuses:

| | meaning |
| --- | --- |
| **✓ PASS** | dependency present / configured |
| **◐ WARN** | runnable but degraded (e.g. mock brain, open egress) — review |
| **✗ FAIL** | must fix before live (e.g. missing EDGAR identity/edgartools) |

Overall **PASS** = cleared for live autonomous operation; **WARN** = runnable,
review the ◐ items; **FAIL** = resolve the ✗ items first.
