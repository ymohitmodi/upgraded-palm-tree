# Tools, MCP & web access — equipping NYX to reach the world

NYX agents act through a **tool layer** (`nyx/tools/`). Every tool call is
guardrailed (output scanned for secrets/injection) and written to the audit
ledger — reaching the outside world is a governed action like everything else.

```python
from nyx.config import load_config
from nyx.tools import build_toolbox

box = build_toolbox(load_config())
print(box.describe())                 # catalog for prompting
box.call("web_fetch", url="https://www.sec.gov/...")
```

Inspect from the CLI: `nyx tools`.

## What ships

| Tool | Backend | Notes |
| --- | --- | --- |
| `web_fetch(url)` | `requests` or stdlib | cached, rate-limited, domain-allowlisted, HTML→text |
| `edgar_financials(ticker)` | `edgartools` (optional) | XBRL balance sheet / income / cash flow |
| `edgar_filings(ticker, form)` | `edgartools` | 10-K, 10-Q, 8-K, Form 4, 13F-HR |
| `edgar_facts(ticker)` | `edgartools` | all standardized XBRL facts (deep/footnote) |
| `mcp.<server>(tool, arguments)` | any MCP server | from `.nyx/mcp.json` |

Tools **degrade gracefully**: if `requests`/`edgartools`/an MCP server isn't
present, the tool returns a structured error instead of crashing the factory.

## ⚠️ Network policy (read this first)

NYX can only reach hosts your environment allows.

- **Claude Code on the web** uses an allowlist. By default it permits package
  registries + GitHub but **denies `sec.gov` and `berkshirehathaway.com`** — so
  live EDGAR/letter fetches will 403 at the proxy. To enable them, configure the
  environment's network policy to allow: `www.sec.gov`, `efts.sec.gov`,
  `data.sec.gov`, `www.berkshirehathaway.com`, and your news sources. See
  https://code.claude.com/docs/en/claude-code-on-the-web.
- **On your own mini-PC** (the intended lights-out deployment) there is no such
  restriction — `nyx ingest-buffett --fetch` and the EDGAR tools work directly.

Everything here is built to run **offline for tests/CI** (injectable transport,
on-disk cache, seeded doctrine) and **live the moment the network is open** — no
code changes needed.

## SEC EDGAR (edgartools)

Same engine as the [edgartools MCP server](https://github.com/sareegpt/edgartools-mcp).
We use it directly as a library (simpler for a Python app), but you can also run
the MCP server (below).

```bash
pip install -e ".[investing]"          # installs edgartools[ai] + requests
export EDGAR_IDENTITY="Your Name your.email@example.com"   # SEC requires this
```
```python
box.call("edgar_financials", ticker="AAPL")
box.call("edgar_facts", ticker="BRK-B")     # footnote-level XBRL
```

## Registering MCP servers (recommended: sec-edgar-mcp)

The recommended SEC server is
[**sec-edgar-mcp**](https://github.com/stefanoamorelli/sec-edgar-mcp) — built on
edgartools, exposing **filings** (10-K/10-Q/8-K + section extraction),
**financials** (balance sheet / income / cash flow, XBRL-parsed), and
**insider trading** (Form 3/4/5), with every response carrying the source SEC
URL. Generate the manifest with `nyx mcp-init` (or
`nyx.tools.mcp.write_sample_manifest(".nyx/mcp.json")`):

```json
{
  "mcpServers": {
    "sec-edgar-mcp": {
      "command": "docker",
      "args": ["run", "-i", "--rm",
               "-e", "SEC_EDGAR_USER_AGENT=Your Name (your@email.com)",
               "stefanoamorelli/sec-edgar-mcp:latest"]
    }
  }
}
```

It runs via Docker over stdio (SEC requires a real `SEC_EDGAR_USER_AGENT` in the
form `Name (email)`); a local mode also exists
(`python -m sec_edgar_mcp.server --transport streamable-http --port 9870`). Each
configured server appears as an `mcp.<name>` tool; `MCPClient` speaks stdio
JSON-RPC (`initialize` → `tools/list` → `tools/call`). NYX's built-in
`edgar_*`/`read_url` tools use the **same edgartools engine** directly, so you
can pick either path.

## Learning from Buffett

```bash
nyx ingest-buffett                     # seed curated deep-value doctrine (offline)
nyx ingest-buffett --fetch --start 1977 --end 2024   # + Berkshire letters (needs network)
nyx memory --recall "durable moat with high ROIC"    # confirm it's in long-term memory
```

`ingest-buffett` writes the doctrine straight into **long-term memory** as
`principle` lessons, so the analyst starts Buffett-shaped; `--fetch` adds sourced
excerpts from the actual shareholder letters when the network allows it.

## The fitness signal: a point-in-time value backtest

`nyx/domains/investing/backtest.py` is what makes "keep evolving to get better at
value investing" *measurable*. `ValueBenchmark` plugs straight into the
Darwin-Gödel engine:

```bash
nyx evolve --suite value -g 30     # evolve the `analyst` genome vs the backtest
nyx backtest                       # show the evolved analyst's picks + risk-adj return
```

How it stays honest:

- **No look-ahead** — the genome only influences *which value factors it weighs*
  (margin of safety, ROIC, leverage, owner-earnings), computed from data known as
  of T. Forward returns are hidden and used only to score the picks.
- **Walk-forward** — it averages over several independent universes, so fitness
  rewards a *robust* doctrine, not a fit to one period's noise (the classic
  backtest trap).
- **Capital preservation priced in** — score = forward return with a heavy
  penalty on downside, matching the constitution's "don't lose money" gate.
- **The doctrine must actually work** — in the data, sound value factors really do
  predict returns, so a genome encoding the Buffett doctrine backtests better and
  evolution discovers that. (Demo: a doctrine analyst returns ~+25% with zero
  downside vs negative for a no-doctrine genome.)

**Live data (fully wired).** When `EDGAR_IDENTITY` is set and `sec.gov` /
`stooq.com` are reachable, the investing capability builds a **real multi-date
walk-forward** (`nyx/domains/investing/data.py`): point-in-time fundamentals from
edgartools (latest 10-K on/before each backtest date, to limit look-ahead) and
realized ~1‑year forward returns from Stooq. It is **resilient by construction** —
a bad ticker is skipped, a garbled price feed parses to nothing rather than
crashing, all factors are validated finite, and a universe with too few clean
companies (`< MIN_COMPANIES`) is refused so z‑scores are never computed on noise.
If any of that is unavailable it transparently falls back to the synthetic
walk‑forward. Preview whichever is active with **`nyx universe`**.

### Investing constitution gates

`nyx/domains/investing/gates.py` adds three values an autonomous allocator must
not break: **no guaranteed returns**, **no un-sourced numbers** (every figure
must trace to a filing — defeats hallucinated numbers), and **margin of safety
required** on any buy thesis. Use `investing_constitution()` to run the factory
with these enforced, or `check_investing(text)` anywhere.

## Scraping etiquette (built in)

Declares a `User-Agent`, rate-limits per host (`web_rate_limit_seconds`), honors
an optional `allowed_domains` allowlist, and caches every fetch so reruns don't
hammer sources. Keep the identity honest and respect each site's terms — SEC in
particular requires a real contact in your identity string.
