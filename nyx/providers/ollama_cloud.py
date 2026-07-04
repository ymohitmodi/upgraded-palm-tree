"""Ollama Cloud provider — the production brain.

Talks to Ollama Cloud's OpenAI-compatible endpoint at ``<host>/v1/chat/completions``
(default host ``https://ollama.com``). Cloud models are addressed by their
``-cloud`` names, e.g. ``qwen3.5-coder:480b-cloud`` or ``glm-5.1:cloud``.

Uses ``requests`` if installed, otherwise falls back to the standard library so
the factory has zero hard dependencies on a fresh mini-PC. Ollama Cloud does not
log or train on prompt/response data.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request

from ..config import Config
from .base import ChatMessage, Completion


class ProviderError(RuntimeError):
    pass


class OllamaCloudProvider:
    name = "ollama-cloud"

    def __init__(self, config: Config):
        if not config.ollama_api_key:
            raise ProviderError("OllamaCloudProvider requires OLLAMA_API_KEY")
        self.config = config
        self.endpoint = f"{config.ollama_host}/v1/chat/completions"

    def chat(
        self,
        model: str,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.2,
        max_tokens: int = 2048,
    ) -> Completion:
        payload = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        data = self._post(payload)
        try:
            text = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:  # pragma: no cover - network shape
            raise ProviderError(f"unexpected response shape: {data!r}") from exc
        usage = data.get("usage", {}) or {}
        return Completion(
            text=text,
            model=model,
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            raw=data,
        )

    def embed(self, model: str, text: str) -> list[float]:  # pragma: no cover - network
        """Return a semantic embedding vector from Ollama Cloud's /v1/embeddings."""
        url = f"{self.config.ollama_host}/v1/embeddings"
        payload = {"model": model, "input": text}
        body = json.dumps(payload).encode("utf-8")
        try:
            import requests  # type: ignore

            resp = requests.post(url, data=body, headers=self._headers(), timeout=60)
            resp.raise_for_status()
            data = resp.json()
        except ImportError:
            req = urllib.request.Request(url, data=body, headers=self._headers(), method="POST")
            with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310 (trusted host)
                data = json.loads(resp.read().decode("utf-8"))
        try:
            return list(data["data"][0]["embedding"])
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError(f"unexpected embeddings shape: {data!r}") from exc

    # -- transport -----------------------------------------------------------
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.config.ollama_api_key}",
            "Content-Type": "application/json",
        }

    def _post(self, payload: dict) -> dict:
        body = json.dumps(payload).encode("utf-8")
        try:
            import requests  # type: ignore

            resp = requests.post(
                self.endpoint, headers=self._headers(), data=body, timeout=120
            )
            if resp.status_code >= 400:
                raise ProviderError(f"HTTP {resp.status_code}: {resp.text[:500]}")
            return resp.json()
        except ImportError:
            return self._post_stdlib(body)

    def _post_stdlib(self, body: bytes) -> dict:
        req = urllib.request.Request(
            self.endpoint, data=body, headers=self._headers(), method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:  # noqa: S310 (trusted host)
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:  # pragma: no cover - network
            detail = exc.read().decode("utf-8", "replace")[:500]
            raise ProviderError(f"HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:  # pragma: no cover - network
            raise ProviderError(f"network error: {exc.reason}") from exc
