"""NYX command-line interface — the operator's console for the dark factory.

    nyx build "<intent>"   run the full SDLC pipeline for a feature/product
    nyx evolve [-g N]      run N generations of agent self-improvement
    nyx doctor             verify config, constitution, brain, and ledger
    nyx constitution       print the loaded constitution
    nyx ledger [--tail N]  show the audit trail (and verify the hash chain)
    nyx status             show recent factory runs
    nyx serve              lights-out: drain a backlog.txt of intents
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .config import load_config
from .constitution import Constitution
from .factory.orchestrator import Factory
from .observability.ledger import AuditLedger


def _banner(cfg) -> str:
    brain = "MOCK (offline)" if cfg.mock_mode else f"Ollama Cloud @ {cfg.ollama_host}"
    return (
        f"NYX v{__version__} — autonomous dark factory\n"
        f"  brain     : {brain}\n"
        f"  autonomy  : {cfg.autonomy}\n"
        f"  fanout    : {cfg.fanout}\n"
        f"  constitution mode: {cfg.constitution_mode}"
    )


def cmd_build(args) -> int:
    cfg = load_config()
    if args.autonomy:
        cfg.autonomy = args.autonomy
    if args.fanout:
        cfg.fanout = args.fanout
    print(_banner(cfg) + "\n")
    factory = Factory(config=cfg)

    def approver(stage: str, summary: str) -> bool:
        if args.yes:
            return True
        if not sys.stdin.isatty():
            return False
        ans = input(f"\nApprove {stage}? [y/N] ").strip().lower()
        return ans in ("y", "yes")

    result = factory.build(args.intent, approver=approver)
    print("\n" + result.summary())
    print("\nMetrics:", result.metrics)
    print("Ledger intact:", result.ledger_ok)
    if args.show:
        for s in result.stages:
            print(f"\n===== {s.stage.upper()} =====\n{s.artifact}")
    return 0 if (result.shipped or result.held_for_approval) else 1


def cmd_run(args) -> int:
    """Autonomous run: pick the matching capability, then plan→learn→decide→evolve→repeat."""
    from .capabilities import CapabilityRunner

    cfg = load_config()
    if args.autonomy:
        cfg.autonomy = args.autonomy
    if args.fanout:
        cfg.fanout = args.fanout
    print(_banner(cfg) + "\n")

    # ONE loop for every goal: route semantically (LLM when live, keyword
    # fallback offline), then drive the capability through the generic runner.
    from .capabilities.router import route
    from .providers import build_provider

    provider = build_provider(cfg)
    cap = route(args.objective, cfg, provider)
    print(f"capability: {cap.name} — {cap.description}\n")
    runner = CapabilityRunner(cap, config=cfg, provider=provider)
    report = runner.run(
        args.objective,
        max_cycles=args.max_cycles or 6,
        evolve_every=args.evolve_every,
        generations=args.generations,
        keep_going=args.keep_going,
    )
    print("\n" + report.summary())
    return 0


def cmd_capabilities(args) -> int:
    """List the goal-specific capabilities NYX can pursue."""
    from .capabilities import all_capabilities, select_for

    select_for("")  # trigger registration of built-ins
    print("Registered capabilities:")
    for cap in all_capabilities():
        print(f"  - {cap.name:16s} {cap.description}")
    if args.objective:
        chosen = select_for(args.objective)
        print(f"\nObjective would route to: {chosen.name if chosen else '(none)'}")
    return 0


def _benchmark_for(suite: str):
    if suite == "swebench":
        from .evolution.benchmarks import default_swebench_suite

        return default_swebench_suite()
    if suite == "value":
        from .domains.investing import ValueBenchmark

        return ValueBenchmark()
    return None  # engine falls back to its reference benchmark


def cmd_evolve(args) -> int:
    from .evolution.engine import EvolutionEngine

    cfg = load_config()
    print(_banner(cfg) + "\n")
    role = args.role
    directives = None
    if args.suite == "value":
        from .domains.investing import INVESTING_DIRECTIVES

        directives = INVESTING_DIRECTIVES
        if role == "coder":  # default → use the analyst for the value suite
            role = "analyst"
    engine = EvolutionEngine(config=cfg, role=role, benchmark=_benchmark_for(args.suite),
                             directive_pool=directives)
    print(f"benchmark: {args.suite} | role: {role}\n")
    report = engine.evolve(generations=args.generations)
    print(
        f"Evolution complete over {report.generations} generations:\n"
        f"  admitted     : {report.admitted}\n"
        f"  rejected     : {report.rejected}\n"
        f"  archive size : {report.archive_size}\n"
        f"  best before  : {report.best_score_before}\n"
        f"  best after   : {report.best_score_after}\n"
        f"  net gain     : {report.gain}"
    )
    return 0


def cmd_bench(args) -> int:
    """Run the SWE-bench-style suite against the current coder agent."""
    from .constitution import Constitution
    from .evolution.archive import Archive
    from .evolution.benchmarks import default_swebench_suite
    from .agents.roles import build_agent
    from .observability.metrics import Metrics
    from .providers import build_provider

    cfg = load_config()
    print(_banner(cfg) + "\n")
    const = Constitution.load(cfg.constitution_path, mode=cfg.constitution_mode)
    provider = build_provider(cfg)
    # Use the best evolved coder genome if one exists, else the production default.
    best = Archive(cfg.evolution_archive).best_for(args.role)
    genome = best.to_genome() if best else None
    agent = build_agent(args.role, cfg, provider, const, metrics=Metrics(), genome=genome)

    suite = default_swebench_suite()
    result = suite.evaluate(agent)
    for r in result.results:
        mark = "✓" if r.passed else "✗"
        print(f"  {mark} {r.id:16s} {('' if r.passed else r.detail)[:60]}")
    print(f"\nSWE-bench score: {result.score:.0%}  ({'evolved' if best else 'default'} genome)")
    return 0


def cmd_memory(args) -> int:
    """Inspect or query the factory's semantic memory (learned lessons)."""
    from .memory import MemoryStore

    cfg = load_config()
    store = MemoryStore(cfg.memory_path)
    if args.consolidate:
        stats = store.consolidate()
        print(f"Consolidation ('sleep') complete: {stats}")
        return 0
    if args.recall:
        lessons = store.recall(args.recall, k=args.tail)
        print(f"Lessons relevant to {args.recall!r}:")
    else:
        lessons = store.all()[: args.tail]
        print(f"Memory: {len(store)} lessons (showing {min(args.tail, len(store))}):")
    for ln in lessons:
        tier = "LT" if ln.tier == "long_term" else "st"
        print(f"  [{tier} {ln.kind:9s} w={ln.weight:>5} uses={ln.uses}] {ln.text[:88]}")
    if not lessons:
        print("  (none yet — run 'nyx run' or 'nyx build' to accumulate lessons)")
    return 0


def cmd_universe(args) -> int:
    """Preview the backtest universe — live EDGAR+prices if reachable, else synthetic."""
    from .domains.investing import default_universe, try_build_universes
    from .domains.investing.capability import DEFAULT_TICKERS
    from .tools import WebFetcher

    cfg = load_config()
    print(_banner(cfg) + "\n")
    fetcher = WebFetcher(cache_dir=cfg.web_cache_dir, user_agent=cfg.user_agent,
                         allowed_domains=cfg.allowed_domains,
                         rate_limit_seconds=cfg.web_rate_limit_seconds)
    universes = try_build_universes(DEFAULT_TICKERS, identity=cfg.edgar_identity, fetcher=fetcher)
    live = universes is not None
    universes = universes or [default_universe()]
    source = ("EDGAR live walk-forward" if live else
              "synthetic (set EDGAR_IDENTITY + allow sec.gov/stooq.com for live data)")
    print(f"Source: {source}")
    for u in universes:
        print(f"\n  as_of {u.as_of}: {len(u.companies)} companies")
        for c in u.companies[: args.limit]:
            print(f"    {c.ticker:8s} mos={c.margin_of_safety:+.2f} roic={c.roic:.2f} "
                  f"d/e={c.debt_to_equity:.2f} oey={c.owner_earnings_yield:.2f}")
    return 0


def cmd_backtest(args) -> int:
    """Backtest the current/evolved analyst genome on the value universe."""
    from .domains.investing import ValueBenchmark
    from .domains.investing.gates import check_investing
    from .evolution.archive import Archive

    cfg = load_config()
    print(_banner(cfg) + "\n")
    best = Archive(cfg.evolution_archive).best_for("analyst")
    genome = best.to_genome() if best else None
    bench = ValueBenchmark()
    res = bench.evaluate(genome)
    label = "evolved" if best else "baseline (run `nyx evolve --suite value` to improve)"
    print(f"Analyst genome: {label}")
    print(f"  picks           : {', '.join(res.picks)}")
    print(f"  portfolio return: {res.portfolio_return:+.2%}")
    print(f"  downside        : {res.downside:+.2%}")
    print(f"  risk-adj score  : {res.score:+.4f}  (return penalized for capital loss)")
    # Demonstrate the investing gates on a couple of memos.
    bad = "Buy SYN01 now — guaranteed 30% risk-free return."
    print(f"\nGate check (bad memo): {check_investing(bad)}")
    return 0


def cmd_tools(args) -> int:
    """List the tools/MCP servers NYX can use, and connectivity status."""
    from .tools import build_toolbox

    cfg = load_config()
    print(_banner(cfg) + "\n")
    box = build_toolbox(cfg, ledger=AuditLedger(cfg.ledger_path))
    print("Available tools:")
    print(box.describe())
    print(f"\nWeb: UA={cfg.user_agent!r}  cache={cfg.web_cache_dir}  "
          f"allowlist={list(cfg.allowed_domains) or 'ALL'}")
    print(f"EDGAR identity set: {bool(cfg.edgar_identity)}  | MCP manifest: {cfg.mcp_manifest}")
    return 0


def cmd_read(args) -> int:
    """Read a long document (URL or file) end-to-end without overflowing context."""
    from pathlib import Path

    from .context import LongDocReader
    from .providers import build_provider

    cfg = load_config()
    src = args.source
    if src.startswith(("http://", "https://")):
        from .tools import WebFetcher

        doc = WebFetcher(cache_dir=cfg.web_cache_dir, user_agent=cfg.user_agent,
                         allowed_domains=cfg.allowed_domains).fetch(src)
        text = doc.text
    else:
        text = Path(src).read_text(encoding="utf-8", errors="replace")

    digest = LongDocReader(cfg, build_provider(cfg)).read(text, source=src)
    print(f"Read {src} in {digest.n_chunks} chunks (nothing truncated).\n")
    print("=== whole-document synthesis ===")
    print(digest.synthesis)
    if args.query:
        print(f"\n=== sections relevant to: {args.query!r} ===")
        for i, sec in enumerate(digest.retrieve(args.query), 1):
            print(f"\n[{i}] {sec[:600]}")
    return 0


def cmd_preflight(args) -> int:
    """Go-live readiness check for running a capability for real."""
    from .capabilities import select_for
    from .readiness import preflight, verdict

    cfg = load_config()
    print(_banner(cfg) + "\n")
    cap = args.capability or (select_for(args.objective).name if args.objective else None)
    checks = preflight(cfg, capability=cap, probe=args.probe)
    mark = {"PASS": "✓", "WARN": "◐", "FAIL": "✗"}
    print(f"Preflight for capability: {cap or 'general'}"
          + (" (with live probe)" if args.probe else "") + "\n")
    for c in checks:
        print(f"  {mark.get(c.status, '?')} {c.name:18s} {c.detail}")
        if c.fix and c.status != "PASS":
            print(f"      ↳ fix: {c.fix}")
    v = verdict(checks)
    print(f"\nReadiness: {v}. " + {
        "PASS": "Cleared for live autonomous operation.",
        "WARN": "Runnable, but review the ◐ items (some features degraded).",
        "FAIL": "Not ready — resolve the ✗ items first.",
    }[v])
    print("Runbook: docs/RUNBOOK.md")
    return 0 if v != "FAIL" else 1


def cmd_eval(args) -> int:
    """Run held-out evaluations, record the score, and show the trend over time."""
    from .evaluation import EvalHarness

    cfg = load_config()
    print(_banner(cfg) + "\n")
    harness = EvalHarness(cfg)
    if args.history:
        from .capabilities import all_capabilities

        for cap in all_capabilities():
            hist = harness.history(cap.name)
            if hist:
                series = "  ".join(f"{r.score:.3f}" for r in hist[-8:])
                print(f"{cap.name:16s} {harness.trend(cap.name)}  [{series}]")
        return 0

    print("Running held-out evaluations (contamination-controlled)…\n")
    for rec in harness.run_all():
        d = harness.delta(rec.capability)
        arrow = "" if d is None else (f"  ({d:+.4f} vs last)" if d else "  (no change)")
        print(f"  {rec.capability:16s} {rec.score:.4f}{arrow}   {rec.detail}")
    print("\nHistory persisted to", cfg.eval_history, "— run again over time to see the trend "
          "(`nyx eval --history`).")
    return 0


def cmd_track(args) -> int:
    """Show the accumulated track record — realized outcomes fed back as memory."""
    from .memory import MemoryStore

    cfg = load_config()
    store = MemoryStore(cfg.memory_path)
    records = [x for x in store.all() if x.kind == "track-record"]
    if not records:
        print("No track record yet. Run `nyx run` to accumulate realized outcomes.")
        return 0
    print(f"Track record ({len(records)} entries):")
    for r in records[: args.tail]:
        print(f"  [w={r.weight:>4}] {r.text[:110]}")
    return 0


def cmd_security_audit(args) -> int:
    """Audit NYX against OWASP LLM Top 10 + Agentic AI threats for this config."""
    from .security.policy import audit

    cfg = load_config()
    print(_banner(cfg) + "\n")
    report = audit(cfg)
    for c in report["controls"]:
        mark = {"ENFORCED": "✓", "PARTIAL": "◐", "ADVISORY": "!"}.get(c.status, "?")
        print(f"  {mark} {c.id:8s} {c.status:8s} {c.name}")
        note = report["notes"].get(c.id)
        if note:
            print(f"      ↳ {note}")
    s = report["summary"]
    print(f"\n{s['enforced']}/{s['total']} enforced, {s['partial']} partial, "
          f"{s['advisory']} advisory.")
    print("See docs/SECURITY.md for the full mapping and honest scope.")
    return 0


def cmd_mcp_init(args) -> int:
    """Write a starter MCP manifest registering a SEC EDGAR server."""
    from .tools.mcp import write_edgartools_manifest, write_sample_manifest

    cfg = load_config()
    server = getattr(args, "server", "edgartools")
    if server == "sec-edgar-mcp":
        identity = cfg.edgar_identity or "Your Name (your@email.com)"
        path = write_sample_manifest(cfg.mcp_manifest, identity=identity)
        print(f"Wrote MCP manifest: {path}")
        print("Registered: sec-edgar-mcp (https://github.com/stefanoamorelli/sec-edgar-mcp)")
        print("Runs via Docker: `docker run -i --rm -e SEC_EDGAR_USER_AGENT=... "
              "stefanoamorelli/sec-edgar-mcp:latest` — filings, XBRL financials, "
              "Form 3/4/5 insider trading, each with the source SEC URL.")
        print("Set SEC_EDGAR_USER_AGENT to 'Name (email)'. Edit the file to add more servers.")
    else:
        identity = cfg.edgar_identity or "Your Name your@email.com"
        path = write_edgartools_manifest(cfg.mcp_manifest, identity=identity)
        print(f"Wrote MCP manifest: {path}")
        print("Registered: edgartools (https://github.com/sareegpt/edgartools-mcp)")
        print("Runs via `python -m edgar.ai` — no Docker; reuses the installed "
              "edgartools[ai]. Exposes XBRL financials, 13F holdings, Form 4 insider "
              "trades, 8-K events, and standardized facts.")
        if not cfg.edgar_identity:
            print("Set EDGAR_IDENTITY='Name email' in .env (SEC requires it).")
    print("NYX calls it via the 'mcp.<name>' tool. Edit the manifest to add more servers.")
    return 0


def cmd_skills(args) -> int:
    """Sync markdown skills from .nyx/skills/ into long-term memory."""
    from .memory import MemoryStore
    from .skills import sync_skills

    cfg = load_config()
    store = MemoryStore(cfg.memory_path)
    n = sync_skills(store, args.dir)
    where = args.dir or "skills/ + .nyx/skills/"
    print(f"Synced {n} skill sections from {where} into long-term memory "
          f"({len(store)} lessons total).")
    if n == 0:
        print("Drop markdown playbooks into skills/ or .nyx/skills/ and re-run.")
    return 0


def cmd_ingest_solopreneur(args) -> int:
    """Seed solopreneur business doctrine into long-term memory."""
    from .domains.solopreneur import seed_principles
    from .memory import MemoryStore

    cfg = load_config()
    store = MemoryStore(cfg.memory_path)
    n = seed_principles(store)
    print(f"Seeded {n} solopreneur principles into long-term memory.")
    print("Every plan/build now recalls business doctrine (distribution, pricing, "
          "validation, retention) alongside engineering lessons.")
    return 0


def cmd_ingest_buffett(args) -> int:
    """Seed Buffett doctrine into long-term memory (and optionally fetch letters)."""
    from .domains.investing import fetch_letters, seed_principles
    from .memory import MemoryStore

    cfg = load_config()
    store = MemoryStore(cfg.memory_path)
    n = seed_principles(store)
    print(f"Seeded {n} Buffett principles into long-term memory.")
    if args.fetch:
        from .tools import WebFetcher

        fetcher = WebFetcher(cache_dir=cfg.web_cache_dir, user_agent=cfg.user_agent,
                             allowed_domains=cfg.allowed_domains,
                             rate_limit_seconds=cfg.web_rate_limit_seconds)
        print(f"Fetching Berkshire letters {args.start}-{args.end} (needs network access)…")
        stats = fetch_letters(fetcher, store, start=args.start, end=args.end)
        print(f"  letters fetched={stats['fetched']} skipped={stats['skipped']}")
    print(f"Memory now holds {len(store)} lessons "
          f"({store.stats()['long_term']} long-term). Use `nyx memory` to inspect.")
    return 0


def cmd_doctor(args) -> int:
    cfg = load_config()
    print(_banner(cfg) + "\n")
    ok = True

    # Constitution
    try:
        const = Constitution.load(cfg.constitution_path, mode=cfg.constitution_mode)
        print(f"✓ constitution: {len(const.principles)} principles, "
              f"{len(const.gates)} gates, {len(const.forbidden)} forbidden")
    except Exception as exc:  # noqa: BLE001
        print(f"✗ constitution failed to load: {exc}")
        ok = False

    # Ledger
    try:
        ledger = AuditLedger(cfg.ledger_path)
        print(f"✓ ledger: {len(ledger.read())} entries, chain intact={ledger.verify()}")
    except Exception as exc:  # noqa: BLE001
        print(f"✗ ledger error: {exc}")
        ok = False

    # Brain
    if cfg.mock_mode:
        print("• brain: MOCK mode (no OLLAMA_API_KEY). Set it in .env to go live.")
    else:
        print(f"• brain: Ollama Cloud configured ({cfg.model('coder')}). "
              "Run 'nyx build' to exercise it.")

    print("\nDoctor:", "healthy ✓" if ok else "issues found ✗")
    return 0 if ok else 1


def cmd_constitution(args) -> int:
    cfg = load_config()
    const = Constitution.load(cfg.constitution_path, mode=cfg.constitution_mode)
    print(f"# {const.meta.get('name')} v{const.meta.get('version')}\n")
    for p in const.principles.values():
        lock = " [immutable]" if p.immutable else ""
        print(f"[{p.id}] ({p.section}) {p.title}{lock}")
    print("\nGates:")
    for g in const.gates.values():
        print(f"  {g.id} @ {g.stage}: requires {', '.join(g.requires)}")
    print("\nForbidden:")
    for f in const.forbidden:
        print(f"  - {f}")
    return 0


def cmd_ledger(args) -> int:
    cfg = load_config()
    ledger = AuditLedger(cfg.ledger_path)
    entries = ledger.tail(args.tail)
    for e in entries:
        print(f"#{e.seq:04d} [{e.decision:5s}] {e.actor:18s} {e.action:22s} {e.rationale[:80]}")
    if args.verify:
        print("\nChain intact:", ledger.verify())
    if not entries:
        print("(ledger empty — run 'nyx build' first)")
    return 0


def cmd_status(args) -> int:
    cfg = load_config()
    ledger = AuditLedger(cfg.ledger_path)
    runs = [e for e in ledger.read() if e.action in ("run_start", "run_end")]
    if not runs:
        print("No runs yet.")
        return 0
    for e in runs[-args.tail * 2:]:
        print(f"#{e.seq:04d} {e.action:10s} {e.rationale[:100]}")
    return 0


def cmd_serve(args) -> int:
    """Lights-out: drain a backlog of intents (one per line)."""
    cfg = load_config()
    print(_banner(cfg) + "\n")
    backlog = Path(args.backlog)
    if not backlog.exists():
        print(f"No backlog at {backlog}. Create it with one intent per line.")
        return 1
    factory = Factory(config=cfg)
    intents = [ln.strip() for ln in backlog.read_text().splitlines() if ln.strip() and not ln.startswith("#")]
    for intent in intents:
        print(f"\n▶ {intent}")
        result = factory.build(intent, approver=lambda *_: cfg.autonomy == "autonomous")
        print(result.summary())
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="nyx", description="NYX — autonomous dark factory")
    p.add_argument("--version", action="version", version=f"nyx {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    b = sub.add_parser("build", help="run the full SDLC pipeline for an intent")
    b.add_argument("intent", help="what to build, in plain language")
    b.add_argument("--autonomy", choices=["assisted", "supervised", "autonomous"])
    b.add_argument("--fanout", type=int, help="agents per stage")
    b.add_argument("--yes", action="store_true", help="auto-approve gated deploys")
    b.add_argument("--show", action="store_true", help="print every stage artifact")
    b.set_defaults(func=cmd_build)

    r = sub.add_parser("run", help="autonomous mission: plan, build, evolve, repeat")
    r.add_argument("objective", help="the high-level objective to pursue")
    r.add_argument("--max-cycles", type=int, default=6, help="cap on build cycles")
    r.add_argument("--evolve-every", type=int, default=2, help="evolve every N cycles (0=never)")
    r.add_argument("--generations", type=int, default=4, help="evolution generations per round")
    r.add_argument("--evolve-role", default="coder", help="which role to evolve")
    r.add_argument("--keep-going", action="store_true", help="re-plan and continue when backlog empties")
    r.add_argument("--autonomy", choices=["assisted", "supervised", "autonomous"])
    r.add_argument("--fanout", type=int)
    r.set_defaults(func=cmd_run)

    e = sub.add_parser("evolve", help="run agent self-improvement")
    e.add_argument("-g", "--generations", type=int, default=5)
    e.add_argument("--role", default="coder")
    e.add_argument("--suite", choices=["reference", "swebench", "value"], default="reference",
                   help="fitness benchmark (swebench=run code in sandbox; value=value backtest)")
    e.set_defaults(func=cmd_evolve)

    bn = sub.add_parser("bench", help="run the SWE-bench-style suite against the coder agent")
    bn.add_argument("--role", default="coder")
    bn.set_defaults(func=cmd_bench)

    m = sub.add_parser("memory", help="inspect or query learned lessons")
    m.add_argument("--recall", help="query memory for lessons relevant to this text")
    m.add_argument("--consolidate", action="store_true",
                   help="run a consolidation 'sleep' pass (decay, abstract, prune)")
    m.add_argument("--tail", type=int, default=20)
    m.set_defaults(func=cmd_memory)

    bt = sub.add_parser("backtest", help="backtest the analyst genome (value suite)")
    bt.set_defaults(func=cmd_backtest)

    uv = sub.add_parser("universe", help="preview the backtest universe (live or synthetic)")
    uv.add_argument("--limit", type=int, default=8, help="companies to show per period")
    uv.set_defaults(func=cmd_universe)

    cp = sub.add_parser("capabilities", help="list pluggable goal capabilities")
    cp.add_argument("objective", nargs="?", help="optional: show which capability handles it")
    cp.set_defaults(func=cmd_capabilities)

    tl = sub.add_parser("tools", help="list available tools / MCP servers")
    tl.set_defaults(func=cmd_tools)

    rd = sub.add_parser("read", help="read a long document (URL/file) without losing context")
    rd.add_argument("source", help="http(s) URL or local file path")
    rd.add_argument("--query", help="optional question to retrieve specific sections")
    rd.set_defaults(func=cmd_read)

    pf = sub.add_parser("preflight", help="go-live readiness check for a capability")
    pf.add_argument("--capability", help="capability name (software|value-investing|advisor)")
    pf.add_argument("--objective", help="an objective to route to a capability instead")
    pf.add_argument("--probe", action="store_true", help="also test live model + data reachability")
    pf.set_defaults(func=cmd_preflight)

    ev = sub.add_parser("eval", help="run held-out evaluations + show score trend over time")
    ev.add_argument("--history", action="store_true", help="show recorded trend, don't run")
    ev.set_defaults(func=cmd_eval)

    tr = sub.add_parser("track", help="show the realized-outcome track record")
    tr.add_argument("--tail", type=int, default=20)
    tr.set_defaults(func=cmd_track)

    sa = sub.add_parser("security-audit", help="audit against OWASP LLM + Agentic threats")
    sa.set_defaults(func=cmd_security_audit)

    mi = sub.add_parser("mcp-init", help="write a starter MCP manifest (SEC EDGAR)")
    mi.add_argument("--server", choices=["edgartools", "sec-edgar-mcp"], default="edgartools",
                    help="edgartools (python -m edgar.ai, no Docker; default) "
                         "or sec-edgar-mcp (Docker)")
    mi.set_defaults(func=cmd_mcp_init)

    sk = sub.add_parser("skills", help="sync markdown skills into long-term memory")
    sk.add_argument("--dir", default=None, help="specific dir (default: skills/ + .nyx/skills/)")
    sk.set_defaults(func=cmd_skills)

    isp = sub.add_parser("ingest-solopreneur",
                         help="seed solopreneur business doctrine into long-term memory")
    isp.set_defaults(func=cmd_ingest_solopreneur)

    ib = sub.add_parser("ingest-buffett", help="seed Buffett doctrine into long-term memory")
    ib.add_argument("--fetch", action="store_true", help="also fetch Berkshire letters (needs network)")
    ib.add_argument("--start", type=int, default=1977)
    ib.add_argument("--end", type=int, default=2024)
    ib.set_defaults(func=cmd_ingest_buffett)

    d = sub.add_parser("doctor", help="verify configuration and health")
    d.set_defaults(func=cmd_doctor)

    c = sub.add_parser("constitution", help="print the loaded constitution")
    c.set_defaults(func=cmd_constitution)

    lg = sub.add_parser("ledger", help="show the audit trail")
    lg.add_argument("--tail", type=int, default=20)
    lg.add_argument("--verify", action="store_true")
    lg.set_defaults(func=cmd_ledger)

    st = sub.add_parser("status", help="show recent factory runs")
    st.add_argument("--tail", type=int, default=5)
    st.set_defaults(func=cmd_status)

    sv = sub.add_parser("serve", help="lights-out: drain backlog.txt")
    sv.add_argument("--backlog", default="backlog.txt")
    sv.set_defaults(func=cmd_serve)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
