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
    """Autonomous mission: plan -> build -> evolve -> adopt -> repeat."""
    from .mission import MissionControl

    cfg = load_config()
    if args.autonomy:
        cfg.autonomy = args.autonomy
    if args.fanout:
        cfg.fanout = args.fanout
    print(_banner(cfg) + "\n")
    control = MissionControl(config=cfg, evolve_role=args.evolve_role)
    report = control.run(
        args.objective,
        max_cycles=args.max_cycles,
        evolve_every=args.evolve_every,
        generations=args.generations,
        keep_going=args.keep_going,
        autonomy=args.autonomy,
    )
    print("\n" + report.summary())
    return 0


def _benchmark_for(suite: str):
    if suite == "swebench":
        from .evolution.benchmarks import default_swebench_suite

        return default_swebench_suite()
    return None  # engine falls back to its reference benchmark


def cmd_evolve(args) -> int:
    from .evolution.engine import EvolutionEngine

    cfg = load_config()
    print(_banner(cfg) + "\n")
    engine = EvolutionEngine(config=cfg, role=args.role, benchmark=_benchmark_for(args.suite))
    print(f"benchmark: {args.suite}\n")
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
        print(f"✓ ledger: {ledger._seq} entries, chain intact={ledger.verify()}")
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
    e.add_argument("--suite", choices=["reference", "swebench"], default="reference",
                   help="fitness benchmark (swebench runs generated code in the sandbox)")
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

    tl = sub.add_parser("tools", help="list available tools / MCP servers")
    tl.set_defaults(func=cmd_tools)

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
