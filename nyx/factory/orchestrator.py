"""The Factory orchestrator — the dark-factory SDLC pipeline.

Drives intent through: explore → design → build → review → test → ship →
operate. Each stage is constitution-gated; build/design use the fan-out swarm.
Outward-facing/irreversible stages (deploy) are gated to the autonomy level.
Everything is audited.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from ..agents.base import Agent, AgentResult
from ..agents.roles import build_agent
from ..config import Config, load_config
from ..constitution import Constitution
from ..observability.ledger import AuditLedger
from ..observability.metrics import Metrics
from ..providers import build_provider
from ..providers.base import Provider
from .fanout import FanOut

Approver = Callable[[str, str], bool]  # (stage, summary) -> approved?


@dataclass
class StageResult:
    stage: str
    artifact: str
    gate: str | None
    passed: bool
    rationale: str
    claims: dict[str, bool] = field(default_factory=dict)
    candidates: int = 1


@dataclass
class FactoryResult:
    intent: str
    stages: list[StageResult] = field(default_factory=list)
    shipped: bool = False
    blocked_at: str | None = None
    held_for_approval: bool = False
    metrics: dict = field(default_factory=dict)
    ledger_ok: bool = True
    findings: list[str] = field(default_factory=list)
    lessons_applied: int = 0

    def artifact(self, stage: str) -> str | None:
        for s in self.stages:
            if s.stage == stage:
                return s.artifact
        return None

    def summary(self) -> str:
        lines = [f"Intent: {self.intent}"]
        for s in self.stages:
            mark = "✓" if s.passed else ("⏸" if self.held_for_approval and s.stage == "deploy" else "✗")
            lines.append(f"  {mark} {s.stage:9s} gate={s.gate or '-':10s} {s.rationale}")
        status = "SHIPPED" if self.shipped else (
            "HELD (awaiting approval)" if self.held_for_approval else f"BLOCKED at {self.blocked_at}"
        )
        lines.append(f"Result: {status}")
        return "\n".join(lines)


# Pipeline: (stage, role, use_fanout)
_PIPELINE = [
    ("explore", "explorer", False),
    ("design", "architect", True),
    ("build", "coder", True),
    ("review", "reviewer", False),
    ("test", "tester", False),
    ("deploy", "deployer", False),
    ("operate", "operator", False),
]


class Factory:
    """The autonomous dark factory."""

    def __init__(
        self,
        config: Config | None = None,
        provider: Provider | None = None,
        constitution: Constitution | None = None,
        ledger: AuditLedger | None = None,
        metrics: Metrics | None = None,
        genomes: dict | None = None,
        memory=None,
    ):
        self.config = config or load_config()
        self.provider = provider or build_provider(self.config)
        self.constitution = constitution or Constitution.load(
            self.config.constitution_path, mode=self.config.constitution_mode
        )
        self.ledger = ledger or AuditLedger(self.config.ledger_path)
        self.metrics = metrics or Metrics()
        # Evolved genomes adopted per role (from the evolution archive). When a
        # role has an adopted genome, agents run with that improved DNA.
        self.genomes: dict = genomes or {}
        # Semantic memory (lessons). Recalled per build and reflected on after.
        self.memory = memory
        self._recalled: list[str] = []

    # -- agent factory -------------------------------------------------------
    def _agent(self, role: str) -> Agent:
        agent = build_agent(
            role,
            self.config,
            self.provider,
            self.constitution,
            ledger=self.ledger,
            metrics=self.metrics,
            genome=self.genomes.get(role),
        )
        agent.lessons = self._recalled  # apply what we've learned
        return agent

    def _compact_context(self, text: str) -> str:
        """Bound the working context carried between stages (short-term memory).

        Like human working memory, capacity is limited: when the running context
        exceeds the budget, keep the head and tail plus salient lines (decisions,
        gates, signatures, requirements) and elide the rest. Cheap, deterministic,
        and offline — no extra model call.
        """
        budget = self.config.context_char_budget
        if budget <= 0 or len(text) <= budget:
            return text
        # Cut on line boundaries so code fences and sentences survive intact.
        head = text[: budget // 2]
        head = head[: head.rfind("\n")] if "\n" in head else head
        tail = text[-(budget // 4):]
        tail = tail[tail.find("\n") + 1:] if "\n" in tail else tail

        salient_kw = ("must", "gate", "block", "valid", "def ", "class ", "error",
                      "security", "requirement", "accept", "test")
        middle = text[len(head): len(text) - len(tail)]
        salient = [ln for ln in middle.splitlines()  # only lines the cut would lose
                   if any(k in ln.lower() for k in salient_kw)]
        keep = "\n".join(salient)[: budget // 4]
        compacted = f"{head}\n…[context compacted]…\n{keep}\n…\n{tail}"
        return compacted[:budget]  # never exceed the stated working-memory budget

    # -- run -----------------------------------------------------------------
    def build(self, intent: str, approver: Approver | None = None) -> FactoryResult:
        """Run the full pipeline for a feature/product intent."""
        self.ledger.append("factory", "run_start", rationale=intent, decision="INFO")
        result = FactoryResult(intent=intent)
        claims: dict[str, bool] = {}
        context = ""

        # Recall relevant lessons from semantic memory and apply them this run.
        if self.memory is not None:
            self._recalled = [lesson.text for lesson in self.memory.recall(intent, k=5)]
            result.lessons_applied = len(self._recalled)
            if self._recalled:
                self.ledger.append(
                    "memory", "recall", rationale=f"{len(self._recalled)} lessons for: {intent[:60]}",
                    decision="INFO",
                )

        judge = self._agent("reviewer")

        for stage, role, use_fanout in _PIPELINE:
            if self.metrics.calls >= self.config.max_calls:
                result.blocked_at = stage
                self.ledger.append("factory", "budget_exhausted", decision="BLOCK")
                break

            agent = self._agent(role)
            task = self._task_for(stage, intent)

            if use_fanout:
                fan = FanOut(judge=judge)
                fr = fan.run(agent, task, context, n=self.config.fanout)
                primary = fr.winner
                n_candidates = len(fr.candidates)
            else:
                primary = agent.run(task, context)
                n_candidates = 1

            # The Security agent co-signs the review stage.
            if stage == "review":
                sec = self._agent("security").run(task, context=primary.text)
                claims.update(sec.claims)
                primary = self._merge(primary, sec)

            claims.update(primary.claims)

            # Don't trust the security agent's self-graded SECURITY_OK: SCAN the
            # actual build code (secrets, injection, dangerous constructs) and let
            # the scanners VETO the gate (fail-closed) regardless of the claim.
            if stage == "review":
                from .verify import verify_security

                build_art = next((s.artifact for s in result.stages if s.stage == "build"),
                                 primary.text)
                sv = verify_security(build_art)
                claims["security_ok"] = bool(claims.get("security_ok", False)) and sv.ok
                result.findings.extend(sv.findings)
                self.ledger.append(
                    "factory", "verify_security",
                    rationale=("clean" if sv.ok else "; ".join(sv.findings))[:100],
                    decision="PASS" if sv.ok else "BLOCK",
                    data={"scanned": True, "findings": sv.findings},
                )

            # Don't trust the tester's self-graded TESTS_PASS: actually EXECUTE
            # the build's code against the tester's tests in the sandbox and set
            # the claim from reality (fail-closed on a real failure).
            if stage == "test":
                from .verify import verify_artifact

                build_art = next((s.artifact for s in result.stages if s.stage == "build"), "")
                vr = verify_artifact(build_art, primary.text)
                if vr.ran:
                    claims["tests_pass"] = vr.passed
                self.ledger.append(
                    "factory", "verify_tests", rationale=vr.detail[:100],
                    decision=("PASS" if vr.passed else "BLOCK") if vr.ran else "INFO",
                    data={"ran": vr.ran, "passed": vr.passed, "verified": vr.ran},
                )

            # Special handling: deploy is gated to autonomy + approval.
            if stage == "deploy":
                held = self._deploy_gate(intent, primary, approver)
                if held:
                    result.held_for_approval = True

            verdict = self.constitution.evaluate(stage, primary.text, claims)
            self.metrics.record_gate(verdict.passed)
            self.ledger.append(
                actor="factory",
                action=f"gate:{stage}",
                rationale=verdict.rationale,
                decision="PASS" if verdict.passed else "BLOCK",
                data={"gate": verdict.gate, "violations": verdict.violations},
            )

            result.stages.append(
                StageResult(
                    stage=stage,
                    artifact=primary.text,
                    gate=verdict.gate,
                    passed=verdict.passed,
                    rationale=verdict.rationale,
                    claims=dict(primary.claims),
                    candidates=n_candidates,
                )
            )

            result.findings.extend(primary.findings)

            # Carry the winning artifact forward as bounded working memory.
            context = self._compact_context(primary.text)

            if not verdict.passed and self.constitution.mode == "block":
                result.blocked_at = stage
                break

            if stage == "deploy" and result.held_for_approval:
                # Stop before operate; the deploy awaits human approval.
                break

        result.shipped = (
            not result.blocked_at
            and not result.held_for_approval
            and any(s.stage == "operate" and s.passed for s in result.stages)
        )
        result.metrics = self.metrics.summary()

        # Reflect: distill durable lessons from this run into semantic memory.
        if self.memory is not None:
            from ..memory import reflect_on_run

            learned = reflect_on_run(result, self.memory)
            if learned:
                self.ledger.append(
                    "memory", "reflect", rationale=f"{len(learned)} lessons learned",
                    decision="INFO",
                )

        result.ledger_ok = self.ledger.verify()
        self.ledger.append(
            "factory",
            "run_end",
            rationale=f"shipped={result.shipped} blocked_at={result.blocked_at}",
            decision="INFO",
            data=result.metrics,
        )
        return result

    # -- helpers -------------------------------------------------------------
    def _deploy_gate(self, intent: str, artifact: AgentResult, approver: Approver | None) -> bool:
        """Return True if the deploy is HELD awaiting human approval."""
        if self.config.autonomy == "autonomous":
            return False  # lights-out: proceed within policy
        # assisted / supervised require explicit approval for outward action (C5)
        if approver is not None and approver("deploy", artifact.text[:200]):
            self.ledger.append("operator(human)", "approve_deploy", decision="PASS")
            return False
        self.ledger.append(
            "factory", "deploy_held", rationale=f"autonomy={self.config.autonomy}", decision="INFO"
        )
        return True

    @staticmethod
    def _merge(primary: AgentResult, secondary: AgentResult) -> AgentResult:
        merged_claims = dict(primary.claims)
        # Security must concur: AND the security_ok claim.
        if "security_ok" in secondary.claims:
            merged_claims["security_ok"] = (
                primary.claims.get("security_ok", True) and secondary.claims["security_ok"]
            )
        primary.claims = merged_claims
        primary.text = primary.text + "\n\n## Security co-sign\n" + secondary.text
        primary.findings = primary.findings + secondary.findings
        return primary

    @staticmethod
    def _task_for(stage: str, intent: str) -> str:
        prompts = {
            "explore": f"Frame the opportunity for: {intent}",
            "design": f"Write the spec and design for: {intent}",
            "build": f"Implement the smallest correct increment for: {intent}",
            "review": f"Review the implementation for: {intent}",
            "test": f"Write and run acceptance tests for: {intent}",
            "deploy": f"Produce a reversible, gated release plan for: {intent}",
            "operate": f"Operate and assure the health of: {intent}",
        }
        return prompts.get(stage, intent)
