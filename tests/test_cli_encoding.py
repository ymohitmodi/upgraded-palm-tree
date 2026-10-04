"""Regression: the CLI must not crash printing check marks when stdout is a cp1252 stream
(redirected output on Windows: Task Scheduler, CI, `> log.txt`)."""
from __future__ import annotations

import io
import sys

from nyx.__main__ import _ensure_utf8_output


def test_ensure_utf8_output_survives_cp1252_streams(monkeypatch):
    out = io.TextIOWrapper(io.BytesIO(), encoding="cp1252")
    err = io.TextIOWrapper(io.BytesIO(), encoding="cp1252")
    monkeypatch.setattr(sys, "stdout", out)
    monkeypatch.setattr(sys, "stderr", err)
    _ensure_utf8_output()
    print("✓ healthy ✗ broken")          # would raise UnicodeEncodeError on cp1252
    sys.stdout.flush()
    assert out.buffer.getvalue().decode("utf-8").startswith("✓ healthy")
