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


# Budget used when a first attempt returned no content because the model was still
# reasoning when its token budget ran out.
REASONING_RETRY_TOKENS = 2048


def _finish_reason(data: dict) -> str:
    try:
        return data["choices"][0].get("finish_reason") or ""
    except (KeyError, IndexError, TypeError, AttributeError):
        return ""


def _parse_tool_calls(message: dict) -> list:  # pragma: no cover - network shape
    """Normalize OpenAI-style message.tool_calls -> [{name, arguments dict}]."""
    calls = []
    for tc in message.get("tool_calls") or []:
        fn = tc.get("function", tc) or {}
        args = fn.get("arguments", {})
        if isinstance(args, str):
            try:
                args = json.loads(args or "{}")
            except ValueError:
                args = {}
        if fn.get("name"):
            calls.append({"name": fn["name"], "arguments": args if isinstance(args, dict) else {}})
    return calls


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
        tools: list | None = None,
    ) -> Completion:
        completion = self._chat_once(model, messages, temperature=temperature,
                                     max_tokens=max_tokens, tools=tools)
        # Reasoning models (qwen3.5, glm-5.x, gpt-oss, deepseek-v4…) emit their
        # chain of thought in a separate `reasoning` field and only fill `content`
        # once they stop thinking. A budget that runs out mid-reasoning therefore
        # returns EMPTY content with finish_reason="length" — which would silently
        # degrade every structured call site (router, injection classifier, factor
        # weights) to its fallback. Give it room to finish, once.
        if not completion.text.strip() and max_tokens < REASONING_RETRY_TOKENS:
            if _finish_reason(completion.raw) == "length":
                completion = self._chat_once(model, messages, temperature=temperature,
                                             max_tokens=REASONING_RETRY_TOKENS, tools=tools)
        return completion

    def _chat_once(
        self,
        model: str,
        messages: list[ChatMessage],
        *,
        temperature: float,
        max_tokens: int,
        tools: list | None,
    ) -> Completion:
        payload = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        if tools:
            payload["tools"] = tools          # OpenAI-style function-calling
        data = self._post(payload)
        try:
            message = data["choices"][0]["message"]
            text = message.get("content") or ""
        except (KeyError, IndexError, TypeError) as exc:  # pragma: no cover - network shape
            raise ProviderError(f"unexpected response shape: {data!r}") from exc
        tool_calls = _parse_tool_calls(message)   # pragma: no cover - network shape
        usage = data.get("usage", {}) or {}
        return Completion(
            text=text,
            model=model,
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            raw=data,
            tool_calls=tool_calls,
        )

    def embed(self, model: str, text: str) -> list[float]:  # pragma: no cover - network placeholder
        """Return a semantic embedding vector from Ollama Cloud's /v1/embeddings."""
        url = f"{self.config.ollama_host}/v1/embeddings"
        payload = {"model": model, "input": text}
        body = json.dumps(payload).encode("utf-8")
        try:
            import requests  # type: ignore

            resp = requests.post(url, data=body, headers=self._headers(),
                                 timeout=self._EMBED_TIMEOUT)
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

    # (connect, read) tuples — NOT a single float. A single timeout applies the
    # same bound to establishing the connection (DNS + TCP + TLS handshake) and to
    # waiting for a response; on a flaky network/VPN/AV-intercepted link the
    # handshake alone can stall well past what's reasonable for "are we connected
    # at all". A short, separate connect timeout makes that class of hang fail
    # fast instead of freezing an unattended multi-hour `nyx run`.
    _CHAT_TIMEOUT = (10, 180)
    _EMBED_TIMEOUT = (10, 60)

<<<<<<< HEAD
    # Transient-failure policy: an unattended multi-hour run WILL hit dropped
    # connections, timeouts, and 429/5xx blips; each must cost seconds, not the
    # mission. Deliberate interrupts (Ctrl+C) are BaseException and always pass.
    _RETRIES = 3
    _BACKOFF = 2.0   # seconds; grows 2s, 8s

=======
>>>>>>> 3e77a8dfc9fe452b0e527b7fa2cf66034062550d
    def _post(self, payload: dict) -> dict:
        body = json.dumps(payload).encode("utf-8")
        try:
            import requests  # type: ignore
<<<<<<< HEAD
=======

            resp = requests.post(
                self.endpoint, headers=self._headers(), data=body, timeout=self._CHAT_TIMEOUT
            )
            if resp.status_code >= 400:
                raise ProviderError(f"HTTP {resp.status_code}: {resp.text[:500]}")
            return resp.json()
>>>>>>> 3e77a8dfc9fe452b0e527b7fa2cf66034062550d
        except ImportError:
            return self._post_stdlib(body)

        import time as _time

        last: Exception | None = None
        for attempt in range(self._RETRIES):
            try:
                resp = requests.post(
                    self.endpoint, headers=self._headers(), data=body,
                    timeout=self._CHAT_TIMEOUT,
                )
                if resp.status_code == 429 or resp.status_code >= 500:
                    last = ProviderError(f"HTTP {resp.status_code}: {resp.text[:200]}")
                elif resp.status_code >= 400:
                    raise ProviderError(f"HTTP {resp.status_code}: {resp.text[:500]}")
                else:
                    return resp.json()
            except (requests.ConnectionError, requests.Timeout) as exc:
                last = exc
            if attempt < self._RETRIES - 1:
                _time.sleep(self._BACKOFF * (4 ** attempt))
        raise ProviderError(f"network failed after {self._RETRIES} attempts: {last}")

    def _post_stdlib(self, body: bytes) -> dict:
        req = urllib.request.Request(
            self.endpoint, data=body, headers=self._headers(), method="POST"
        )
        try:
            # stdlib urlopen only accepts a single timeout float — best effort.
            with urllib.request.urlopen(req, timeout=180) as resp:  # noqa: S310 (trusted host)
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:  # pragma: no cover - network
            detail = exc.read().decode("utf-8", "replace")[:500]
            raise ProviderError(f"HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:  # pragma: no cover - network
            raise ProviderError(f"network error: {exc.reason}") from exc
