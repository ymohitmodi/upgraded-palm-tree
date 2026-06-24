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

## Registering MCP servers

Drop a manifest at `.nyx/mcp.json` (same shape as Claude Desktop's `mcpServers`):

```json
{
  "mcpServers": {
    "edgar": {
      "command": "python", "args": ["-m", "edgar.ai"],
      "env": { "EDGAR_IDENTITY": "Your Name your.email@example.com" }
    }
  }
}
```

Generate a starter with `nyx.tools.mcp.write_sample_manifest(".nyx/mcp.json")`.
Each server appears as an `mcp.<name>` tool; `MCPClient` speaks stdio JSON-RPC
(`initialize` → `tools/list` → `tools/call`).

## Learning from Buffett

```bash
nyx ingest-buffett                     # seed curated deep-value doctrine (offline)
nyx ingest-buffett --fetch --start 1977 --end 2024   # + Berkshire letters (needs network)
nyx memory --recall "durable moat with high ROIC"    # confirm it's in long-term memory
```

`ingest-buffett` writes the doctrine straight into **long-term memory** as
`principle` lessons, so the analyst starts Buffett-shaped; `--fetch` adds sourced
excerpts from the actual shareholder letters when the network allows it.

## Scraping etiquette (built in)

Declares a `User-Agent`, rate-limits per host (`web_rate_limit_seconds`), honors
an optional `allowed_domains` allowlist, and caches every fetch so reruns don't
hammer sources. Keep the identity honest and respect each site's terms — SEC in
particular requires a real contact in your identity string.
