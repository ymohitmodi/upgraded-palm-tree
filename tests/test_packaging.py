"""Guard the install surface: requirements, env template, and installer stay in
sync with what the code actually reads."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_requirements_files_exist_and_list_core_deps():
    req = (ROOT / "requirements.txt").read_text()
    assert "edgartools" in req and "requests" in req and "PyYAML" in req
    dev = (ROOT / "requirements-dev.txt").read_text()
    assert "-r requirements.txt" in dev and "pytest" in dev and "ruff" in dev


def test_installer_is_executable_and_sane():
    inst = ROOT / "install.sh"
    assert inst.exists()
    body = inst.read_text()
    assert 'pip install -e ".[investing,dev]"' in body
    assert "nyx preflight" in body and "nyx doctor" in body
    # executable bit set
    assert inst.stat().st_mode & 0o111


def test_env_example_documents_live_knobs():
    env = (ROOT / ".env.example").read_text()
    for key in ("OLLAMA_API_KEY", "EDGAR_IDENTITY", "NYX_MODEL_EMBED",
                "NYX_ALLOWED_DOMAINS", "NYX_MCP_MANIFEST", "NYX_EVAL_HISTORY"):
        assert key in env, f"{key} missing from .env.example"


def test_env_example_keys_are_read_by_config():
    """Every NYX_* key documented in .env.example must be consumed by config.py
    (prevents documenting knobs that do nothing)."""
    import re

    env_keys = set(re.findall(r"^(NYX_[A-Z_]+)=", (ROOT / ".env.example").read_text(),
                              re.MULTILINE))
    cfg_src = (ROOT / "nyx" / "config.py").read_text()
    unread = {k for k in env_keys if k not in cfg_src}
    assert not unread, f"documented but unused env keys: {unread}"
