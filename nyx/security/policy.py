"""Security policy & self-audit — map controls to OWASP and check live config.

Covers the **OWASP Top 10 for LLM Applications (2025)** and the **OWASP Agentic
AI threats**. Each control names where it is enforced in code, and ``audit()``
folds in live-config checks so an operator can see, concretely, whether the
running configuration clears a realistic bar (and where it is only advisory).
"""
from __future__ import annotations

from dataclasses import dataclass

ENFORCED, PARTIAL, ADVISORY = "ENFORCED", "PARTIAL", "ADVISORY"


@dataclass
class Control:
    id: str
    name: str
    mitigation: str
    where: str
    status: str


# OWASP LLM Top 10 (2025)
_LLM = [
    Control("LLM01", "Prompt injection",
            "Untrusted content delimited as data; heuristic + LLM injection classifier on "
            "external tool output; evolution rejects governance-weakening genomes",
            "security/injection_classifier.py, guardrails.py", ENFORCED),
    Control("LLM02", "Sensitive information disclosure",
            "Secret scan + redaction on tool output, agent output, and ledger writes",
            "security/guardrails.py, tools/registry.py", ENFORCED),
    Control("LLM03", "Supply chain",
            "Dependency-light core; third-party MCP output treated as untrusted/external",
            "tools/mcp.py", PARTIAL),
    Control("LLM04", "Data & model poisoning",
            "External content stored trusted=False; cannot form long-term doctrine; "
            "PDF/mojibake guard on ingestion",
            "memory.py, context.py, domains/investing/buffett.py", ENFORCED),
    Control("LLM05", "Improper output handling",
            "Generated code executed only in the sandbox; tool output injection-neutralized",
            "security/sandbox.py, tools/registry.py", ENFORCED),
    Control("LLM06", "Excessive agency",
            "Per-capability least-privilege tools; deploy gated to autonomy + human approval; "
            "ALL FIVE gates verified against the artifact/ledger, not self-graded "
            "(spec/security/tests/deploy/audit)",
            "capabilities/*, constitution.py, factory/verify.py", ENFORCED),
    Control("LLM07", "System-prompt leakage",
            "System preamble kept minimal; output scanned for verbatim preamble leakage",
            "agents/base.py", PARTIAL),
    Control("LLM08", "Vector & embedding weakness",
            "Recall down-weights untrusted memories; poisoned content can't outrank doctrine",
            "memory.py", PARTIAL),
    Control("LLM09", "Misinformation",
            "Investing gates require sourced numbers + forbid guarantees; test claims verified",
            "domains/investing/gates.py, factory/verify.py", PARTIAL),
    Control("LLM10", "Unbounded consumption",
            "Shared call/spend budget; per-host rate limits; crawl/chunk bounds; MCP + "
            "ReAct step caps",
            "config.py, capabilities/runner.py, tools/*", ENFORCED),
]

# OWASP Agentic AI threats
_AGENTIC = [
    Control("AGT-T1", "Memory poisoning",
            "External memories are trusted=False, injection-screened, capped short-term, "
            "and excluded from doctrine consolidation",
            "memory.py, context.py", ENFORCED),
    Control("AGT-T2", "Tool misuse",
            "Typed ArgSpec validation + guardrailed, audited calls",
            "tools/registry.py", ENFORCED),
    Control("AGT-T3", "Privilege compromise",
            "Least-privilege allowlist per capability (wildcards for MCP)",
            "tools/registry.py, capabilities/*", ENFORCED),
    Control("AGT-T4", "Resource overload",
            "One mission budget; rate limits; bounded crawl/chunk/steps",
            "config.py, tools/web.py", ENFORCED),
    Control("AGT-T5", "Cascading hallucination",
            "All five constitution gates verified against reality (executed tests, "
            "scanned security, structural spec/deploy, ledger-derived audit) + fan-out judge",
            "factory/verify.py", ENFORCED),
    Control("AGT-T6", "Intent / goal manipulation",
            "Constitution forbidden list + injection defense on inputs",
            "constitution.py", PARTIAL),
    Control("AGT-T7", "Repudiation / untraceability",
            "Hash-chained append-only audit ledger; verify() detects tampering",
            "observability/ledger.py", ENFORCED),
    Control("AGT-T8", "Human-in-the-loop bypass",
            "Deploy gate + autonomy levels; irreversible actions require approval",
            "factory/orchestrator.py, constitution.py", ENFORCED),
    Control("AGT-T9", "Unsafe egress / SSRF",
            "Scheme + domain allowlist + resolution guard (no private/metadata addrs)",
            "security/egress.py", ENFORCED),
]

CONTROLS = _LLM + _AGENTIC


def audit(config) -> dict:
    """Run live-config checks and return a report with per-control state + notes."""
    notes: dict[str, str] = {}
    rows = [Control(**{**c.__dict__}) for c in CONTROLS]
    by_id = {c.id: c for c in rows}

    # LLM10 / AGT-T4: a real budget must be set.
    if getattr(config, "max_calls", 0) <= 0:
        by_id["LLM10"].status = ADVISORY
        notes["LLM10"] = "max_calls not set — no spend budget"

    # AGT-T9 / SSRF: on an open network an empty allowlist means fetch-anywhere.
    if not getattr(config, "allowed_domains", ()):  # empty
        notes["AGT-T9"] = ("allowed_domains empty: SSRF resolution guard still blocks "
                           "private/metadata IPs, but consider an allowlist for autonomy")

    # LLM06: fail-closed governance.
    if getattr(config, "constitution_mode", "block") != "block":
        by_id["LLM06"].status = PARTIAL
        notes["LLM06"] = f"constitution_mode={config.constitution_mode} (not fail-closed 'block')"

    # LLM01: the LLM classifier only activates with a live brain.
    if getattr(config, "mock_mode", True):
        notes["LLM01"] = "mock mode: heuristic injection filter only (LLM classifier needs a key)"

    summary = {
        "enforced": sum(1 for c in rows if c.status == ENFORCED),
        "partial": sum(1 for c in rows if c.status == PARTIAL),
        "advisory": sum(1 for c in rows if c.status == ADVISORY),
        "total": len(rows),
    }
    return {"controls": rows, "notes": notes, "summary": summary}
