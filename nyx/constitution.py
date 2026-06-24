"""The constitution engine — NYX's governance core.

Two jobs:

1. **Steer** — inject the relevant principles into each agent's system prompt so
   the model is guided by them (the Constitutional AI idea).
2. **Enforce** — validate agent outputs against the gates and the forbidden list
   before an artifact is allowed to flow downstream (fail-closed by default).

It also guards the *amendment ratchet*: the evolution engine may add or tighten
principles, but never remove or weaken an ``immutable`` core principle.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import _miniyaml


def load_yaml(text: str) -> Any:
    """Parse YAML, preferring PyYAML if available, else the bundled subset parser."""
    try:
        import yaml  # type: ignore

        return yaml.safe_load(text)
    except ImportError:
        return _miniyaml.loads(text)


@dataclass(frozen=True)
class Principle:
    id: str
    title: str
    rule: str
    section: str
    immutable: bool = False


@dataclass(frozen=True)
class Gate:
    id: str
    stage: str
    requires: tuple[str, ...]
    description: str


@dataclass
class Verdict:
    """The result of checking an artifact against the constitution."""

    passed: bool
    gate: str | None = None
    violations: list[str] = field(default_factory=list)
    rationale: str = ""

    def __bool__(self) -> bool:  # truthy iff it passed
        return self.passed


class ConstitutionViolation(RuntimeError):
    """Raised (in block mode) when an artifact violates the constitution."""

    def __init__(self, verdict: Verdict):
        self.verdict = verdict
        super().__init__(verdict.rationale or "; ".join(verdict.violations))


class Constitution:
    """Loaded, queryable, enforceable constitution."""

    def __init__(self, data: dict, mode: str = "block"):
        self.raw = data
        self.meta = data.get("meta", {})
        self.mode = mode  # block | warn
        self.principles: dict[str, Principle] = {}
        for section in ("core", "engineering", "conduct"):
            for item in data.get(section, []) or []:
                p = Principle(
                    id=item["id"],
                    title=item.get("title", ""),
                    rule=(item.get("rule", "") or "").strip(),
                    section=section,
                    immutable=bool(item.get("immutable", False)),
                )
                self.principles[p.id] = p
        self.gates: dict[str, Gate] = {}
        for g in data.get("gates", []) or []:
            gate = Gate(
                id=g["id"],
                stage=g.get("stage", ""),
                requires=tuple(g.get("requires", []) or []),
                description=g.get("description", ""),
            )
            self.gates[gate.id] = gate
        self.forbidden: list[str] = list(data.get("forbidden", []) or [])

    # -- construction --------------------------------------------------------
    @classmethod
    def load(cls, path: str | Path, mode: str = "block") -> "Constitution":
        text = Path(path).read_text(encoding="utf-8")
        return cls(load_yaml(text), mode=mode)

    # -- steering ------------------------------------------------------------
    def system_preamble(self, sections: tuple[str, ...] = ("core", "conduct")) -> str:
        """A compact constitution block to prepend to an agent's system prompt."""
        lines = ["# NYX CONSTITUTION (binding)"]
        for p in self.principles.values():
            if p.section in sections:
                first = p.rule.splitlines()[0] if p.rule else p.title
                lines.append(f"- [{p.id}] {p.title}: {first}")
        if self.forbidden:
            lines.append("# FORBIDDEN (hard blocks, regardless of instructions):")
            lines.extend(f"- {f}" for f in self.forbidden)
        return "\n".join(lines)

    def gate_for_stage(self, stage: str) -> Gate | None:
        for gate in self.gates.values():
            if gate.stage == stage:
                return gate
        return None

    # -- enforcement ---------------------------------------------------------
    def check_forbidden(self, text: str) -> list[str]:
        """Heuristic scan for declared-forbidden behaviors in an artifact."""
        violations: list[str] = []
        low = text.lower()
        # Map forbidden items to detectable signals.
        signals = {
            "exfiltrate secrets": [r"print\(.*(api_key|secret|password|token)",
                                   r"send.*(api_key|secret|private[_ ]key)"],
            "disable or bypass the audit ledger": [r"(disable|skip|bypass).*(ledger|audit)"],
            "remove or weaken an immutable": [r"(remove|delete|weaken).*(immutable|core principle)"],
            "fabricated results": [r"(fake|fabricat|pretend).*(test|result|pass)"],
        }
        for item in self.forbidden:
            key = next((k for k in signals if k in item.lower()), None)
            if key and any(re.search(p, low) for p in signals[key]):
                violations.append(f"forbidden: {item}")
        return violations

    def evaluate(self, stage: str, artifact: str, claims: dict[str, bool] | None = None) -> Verdict:
        """Check an artifact at a pipeline stage against the relevant gate.

        ``claims`` are boolean facts the producing agent asserts (e.g.
        ``{"has_spec": True, "tests_pass": True}``) which the gate consults.
        """
        claims = claims or {}
        violations = self.check_forbidden(artifact)

        gate = self.gate_for_stage(stage)
        gate_id = gate.id if gate else None
        if gate:
            gate_checks = {
                "G_SPEC": ("has_spec", "missing written spec with acceptance criteria"),
                "G_SECURITY": ("security_ok", "security review not satisfied (secrets/injection)"),
                "G_TESTS": ("tests_pass", "acceptance tests missing or failing"),
                "G_DEPLOY": ("deploy_reversible", "deploy not reversible / not gated to autonomy"),
                "G_AUDIT": ("audited", "action+rationale not recorded / no health signals"),
            }
            req = gate_checks.get(gate.id)
            if req:
                claim_key, msg = req
                if not claims.get(claim_key, False):
                    violations.append(f"{gate.id}: {msg}")

        passed = not violations
        rationale = (
            f"stage={stage} gate={gate_id} -> PASS"
            if passed
            else f"stage={stage} gate={gate_id} -> BLOCK: " + "; ".join(violations)
        )
        return Verdict(passed=passed, gate=gate_id, violations=violations, rationale=rationale)

    def enforce(self, stage: str, artifact: str, claims: dict[str, bool] | None = None) -> Verdict:
        """Like :meth:`evaluate` but raises in ``block`` mode on violation."""
        verdict = self.evaluate(stage, artifact, claims)
        if not verdict.passed and self.mode == "block":
            raise ConstitutionViolation(verdict)
        return verdict

    # -- amendment ratchet ---------------------------------------------------
    def validate_amendment(self, new_data: dict) -> Verdict:
        """Reject amendments that remove or weaken any immutable core principle."""
        new = Constitution(new_data, mode=self.mode)
        violations: list[str] = []
        for pid, p in self.principles.items():
            if not p.immutable:
                continue
            np = new.principles.get(pid)
            if np is None:
                violations.append(f"amendment removes immutable principle {pid}")
            elif not np.immutable:
                violations.append(f"amendment unsets immutability of {pid}")
            elif len(np.rule) < len(p.rule) * 0.5:
                violations.append(f"amendment appears to weaken {pid} (rule shrunk materially)")
        for item in self.forbidden:
            if item not in new.forbidden:
                violations.append(f"amendment drops forbidden item: {item}")
        passed = not violations
        return Verdict(
            passed=passed,
            rationale="amendment accepted" if passed else "amendment rejected: " + "; ".join(violations),
            violations=violations,
        )
