"""Model providers — the factory's brain."""
from __future__ import annotations

from ..config import Config
from .base import ChatMessage, Provider, Completion
from .mock import MockProvider
from .ollama_cloud import OllamaCloudProvider


def build_provider(config: Config) -> Provider:
    """Return the real Ollama Cloud provider, or a deterministic mock when no key."""
    if config.mock_mode:
        return MockProvider(config)
    return OllamaCloudProvider(config)


__all__ = [
    "ChatMessage",
    "Provider",
    "Completion",
    "MockProvider",
    "OllamaCloudProvider",
    "build_provider",
]
