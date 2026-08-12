# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""LLM provider adapters — OpenAI, Anthropic, Ollama, llama.cpp, custom.

All adapters implement :class:`LLMProvider` and can be passed directly
to ``crp.Client(provider=...)``.

Usage::

    from crp.providers import OpenAIAdapter, OllamaAdapter

    provider = OpenAIAdapter(model="gpt-4o")
    # or
    provider = OllamaAdapter(model="llama3.1")
"""

from crp.providers.base import LLMProvider
from crp.providers.custom import CustomProvider
from crp.providers.discovery import (
    DetectedModel,
    DetectedRuntime,
    DiscoveryReport,
    ModelState,
    RuntimeKind,
    discover_local_llms,
)
from crp.providers.llamacpp import LlamaCppAdapter
from crp.providers.ollama import OllamaAdapter
from crp.providers.openai import OpenAIAdapter

# Lazy import for optional dependency: Anthropic
def __getattr__(name: str):
    if name == "AnthropicAdapter":
        from crp.providers.anthropic import AnthropicAdapter
        return AnthropicAdapter
    raise AttributeError(f"module 'crp.providers' has no attribute {name!r}")

# Convenience alias matching docs
CallableAdapter = CustomProvider
BaseAdapter = LLMProvider

__all__ = [
    "LLMProvider",
    "BaseAdapter",
    "OpenAIAdapter",
    "AnthropicAdapter",
    "OllamaAdapter",
    "LlamaCppAdapter",
    "CustomProvider",
    "CallableAdapter",
    # Local-LLM discovery
    "discover_local_llms",
    "DiscoveryReport",
    "DetectedRuntime",
    "DetectedModel",
    "RuntimeKind",
    "ModelState",
]
