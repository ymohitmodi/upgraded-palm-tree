"""Shared fixtures. Force MOCK mode + isolated state so tests are hermetic."""
from __future__ import annotations

import os

import pytest

from nyx.config import load_config


@pytest.fixture(autouse=True)
def _force_mock(monkeypatch, tmp_path):
    # No key -> deterministic MockProvider.
    monkeypatch.delenv("OLLAMA_API_KEY", raising=False)
    monkeypatch.setenv("NYX_LEDGER", str(tmp_path / "audit.ledger.jsonl"))
    monkeypatch.setenv("NYX_EVOLUTION_ARCHIVE", str(tmp_path / "archive"))
    yield


@pytest.fixture
def config(tmp_path):
    cfg = load_config(dotenv=False)
    cfg.ledger_path = str(tmp_path / "audit.ledger.jsonl")
    cfg.evolution_archive = str(tmp_path / "archive")
    cfg.fanout = 3
    return cfg


@pytest.fixture
def constitution_path():
    # The repo's real constitution drives the tests.
    here = os.path.dirname(os.path.dirname(__file__))
    return os.path.join(here, "constitution", "constitution.yaml")
