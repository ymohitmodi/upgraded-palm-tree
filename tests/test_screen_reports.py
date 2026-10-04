"""Never-fail hardening + reviewable output: local-first embeddings, provider
retry on transient network errors, market-percentile context, and the
timestamped shortlist reports."""
from __future__ import annotations

import pytest

from nyx.config import Config
from nyx.domains.investing.assess import (
    Assessment,
    market_context,
    percentile_of,
    write_shortlist_reports,
)
from nyx.domains.investing.backtest import Company
from nyx.embeddings import HashingEmbedder, ProviderEmbedder, embedder_for
from nyx.providers.ollama_cloud import OllamaCloudProvider, ProviderError


# -- local-first embeddings ---------------------------------------------------
def test_embeddings_default_to_local_even_with_live_key(monkeypatch):
    """Cloud embeddings put a network call inside every remember/recall — the
    hang that froze a mission. Local hashing must be the default; cloud opt-in."""
    monkeypatch.delenv("NYX_EMBEDDINGS", raising=False)

    class P:
        def embed(self, model, text):
            return [0.1]

    cfg = Config(ollama_api_key="live-key")
    assert isinstance(embedder_for(cfg, P()), HashingEmbedder)
    monkeypatch.setenv("NYX_EMBEDDINGS", "cloud")
    assert isinstance(embedder_for(cfg, P()), ProviderEmbedder)


def test_local_embedder_is_fast_enough_for_big_stores():
    import time
    emb = HashingEmbedder()
    t0 = time.perf_counter()
    for i in range(300):
        emb.embed(f"lesson {i}: a durable moat protects returns on invested capital")
    assert time.perf_counter() - t0 < 2.0     # hundreds of lessons in well under a blink


# -- provider retry -----------------------------------------------------------
def _no_sleep(monkeypatch):
    import time
    monkeypatch.setattr(time, "sleep", lambda *_: None)


def test_transient_connection_errors_are_retried(monkeypatch):
    import requests
    _no_sleep(monkeypatch)
    provider = OllamaCloudProvider(Config(ollama_api_key="k"))
    calls = {"n": 0}

    class OK:
        status_code = 200

        def json(self):
            return {"choices": [{"message": {"content": "hi"}, "finish_reason": "stop"}],
                    "usage": {}}

    def flaky_post(url, headers=None, data=None, timeout=None):
        calls["n"] += 1
        if calls["n"] < 3:
            raise requests.ConnectionError("simulated drop")
        return OK()

    monkeypatch.setattr(requests, "post", flaky_post)
    assert provider._post({"model": "m"})["choices"]
    assert calls["n"] == 3                      # two failures healed by retries


def test_persistent_failure_raises_provider_error_not_hang(monkeypatch):
    import requests
    _no_sleep(monkeypatch)
    provider = OllamaCloudProvider(Config(ollama_api_key="k"))

    def dead_post(url, headers=None, data=None, timeout=None):
        raise requests.Timeout("simulated dead network")

    monkeypatch.setattr(requests, "post", dead_post)
    with pytest.raises(ProviderError, match="network failed after"):
        provider._post({"model": "m"})


def test_client_errors_do_not_retry(monkeypatch):
    """A 404 (bad model name) is not transient — retrying would just triple cost."""
    import requests
    _no_sleep(monkeypatch)
    provider = OllamaCloudProvider(Config(ollama_api_key="k"))
    calls = {"n": 0}

    class NotFound:
        status_code = 404
        text = "model not found"

    def post(url, headers=None, data=None, timeout=None):
        calls["n"] += 1
        return NotFound()

    monkeypatch.setattr(requests, "post", post)
    with pytest.raises(ProviderError, match="404"):
        provider._post({"model": "m"})
    assert calls["n"] == 1


# -- percentile context -------------------------------------------------------
def _co(t, mos):
    price = 100.0
    return Company(ticker=t, price=price, intrinsic_value=price / (1 - mos),
                   roic=0.1, debt_to_equity=0.5, owner_earnings_yield=0.05)


def test_percentiles_place_a_company_against_all_alternatives():
    assert percentile_of([1, 2, 3, 4], 5) == 100
    assert percentile_of([1, 2, 3, 4], 0) == 0
    universe = [_co(f"T{i}", mos) for i, mos in enumerate([-0.2, 0.0, 0.1, 0.3])]
    ctx = market_context(universe[-1], universe)
    assert "p75" in ctx and "alternatives" in ctx


# -- timestamped shortlist reports --------------------------------------------
def test_shortlist_reports_written_to_timestamped_dir(tmp_path):
    finalists = [
        Assessment(ticker="AAA", factor_score=1.2, llm_score=8.0, final_score=0.9,
                   rationale="Wide moat at a 40% discount to intrinsic value.",
                   held_by=["BRK-B"], market_context="vs all 3: margin-of-safety p90"),
        Assessment(ticker="BBB", factor_score=0.8, llm_score=6.0, final_score=0.7,
                   rationale="Cheap but covenant-heavy balance sheet."),
    ]
    companies = {"AAA": _co("AAA", 0.4), "BBB": _co("BBB", 0.2)}
    out = write_shortlist_reports(tmp_path, finalists, as_of="2026-07-12",
                                  companies=companies, principles="- Demand a margin of safety",
                                  evidence_fn=lambda t: f"footnote excerpt for {t}",
                                  funnel="3 screened → 2 deep-read")
    files = sorted(p.name for p in out.glob("*.md"))
    assert files == ["00-summary.md", "01-AAA.md", "02-BBB.md"]
    summary = (out / "00-summary.md").read_text(encoding="utf-8")
    assert "AAA" in summary and "Not investment advice" in summary
    aaa = (out / "01-AAA.md").read_text(encoding="utf-8")
    assert "Wide moat" in aaa and "BRK-B" in aaa
    assert "margin-of-safety p90" in aaa and "footnote excerpt for AAA" in aaa
    assert "Margin of safety: +40.0%" in aaa
    # timestamped parent: reports/<stamp>/ under the given root
    assert out.parent.name == "reports"
