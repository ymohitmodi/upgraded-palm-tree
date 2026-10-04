"""Chat/embed calls use a (connect, read) timeout tuple, not a single float — a
single float bounds connect and read the same way, so a stalled TLS handshake
(the exact hang that killed an unattended run) waits the full read-timeout
before failing. A short, separate connect timeout fails that class of hang fast.
"""
from __future__ import annotations

from nyx.config import Config
from nyx.providers.ollama_cloud import OllamaCloudProvider


class _FakeResponse:
    status_code = 200

    def json(self):
        return {"choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
                "usage": {}}

    def raise_for_status(self):
        pass


class _FakeEmbedResponse:
    status_code = 200

    def json(self):
        return {"data": [{"embedding": [0.1, 0.2]}]}

    def raise_for_status(self):
        pass


def test_chat_uses_connect_read_timeout_tuple(monkeypatch):
    provider = OllamaCloudProvider(Config(ollama_api_key="k"))
    captured = {}

    def fake_post(url, headers=None, data=None, timeout=None):
        captured["timeout"] = timeout
        return _FakeResponse()

    import requests
    monkeypatch.setattr(requests, "post", fake_post)
    provider._post({"model": "m"})
    assert isinstance(captured["timeout"], tuple) and len(captured["timeout"]) == 2
    connect, read = captured["timeout"]
    assert connect <= 15                      # fails fast on a stalled handshake
    assert read > connect                     # generation is allowed much longer


def test_embed_uses_connect_read_timeout_tuple(monkeypatch):
    provider = OllamaCloudProvider(Config(ollama_api_key="k"))
    captured = {}

    def fake_post(url, data=None, headers=None, timeout=None):
        captured["timeout"] = timeout
        return _FakeEmbedResponse()

    import requests
    monkeypatch.setattr(requests, "post", fake_post)
    provider.embed("m", "text")
    assert isinstance(captured["timeout"], tuple) and len(captured["timeout"]) == 2
    assert captured["timeout"][0] <= 15
