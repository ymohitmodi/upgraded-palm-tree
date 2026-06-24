"""Constrained execution boundary for generated code.

Building and testing a dark factory's output means running code the agents
wrote. That code is untrusted. This sandbox runs it in a *fresh temp directory*,
as a separate process, with a timeout and no inherited environment — a pragmatic
boundary for a mini-PC. For stronger isolation wire this to a container/VM; the
interface stays the same.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass
class SandboxResult:
    ok: bool
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False


def run_sandboxed(
    code: str,
    *,
    timeout: float = 15.0,
    filename: str = "candidate.py",
    extra_files: dict[str, str] | None = None,
) -> SandboxResult:
    """Execute ``code`` in an isolated temp dir as a subprocess.

    No network is granted by NYX; the process inherits a minimal environment and
    runs with the temp dir as its working directory so it cannot touch the repo.
    """
    workdir = Path(tempfile.mkdtemp(prefix="nyx_sandbox_"))
    try:
        for name, content in (extra_files or {}).items():
            (workdir / name).write_text(content, encoding="utf-8")
        (workdir / filename).write_text(code, encoding="utf-8")
        try:
            proc = subprocess.run(
                [sys.executable, "-I", filename],  # -I: isolated mode, ignore env
                cwd=workdir,
                capture_output=True,
                text=True,
                timeout=timeout,
                env={"PATH": "", "PYTHONHASHSEED": "0"},
            )
        except subprocess.TimeoutExpired as exc:
            return SandboxResult(
                ok=False,
                returncode=-1,
                stdout=exc.stdout or "",
                stderr=(exc.stderr or "") + "\n[sandbox] timed out",
                timed_out=True,
            )
        return SandboxResult(
            ok=proc.returncode == 0,
            returncode=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
        )
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
