# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Shared provider auto-detection for the CRP agent templates.

Every template calls :func:`resolve_provider` instead of hand-rolling its own
provider setup. Resolution order (first available wins):

1. ``CRP_LMSTUDIO_URL`` / a local LM Studio server on ``localhost:1234``
2. ``OPENAI_API_KEY`` set
3. ``ANTHROPIC_API_KEY`` set
4. A local Ollama server on ``localhost:11434``

If none are available, raises a clear, actionable error instead of silently
falling back to a mock — these templates are meant to prove CRP works against
a real model, not to demonstrate a scripted fake.
"""

from __future__ import annotations

import os
import urllib.request


def _reachable(url: str, timeout: float = 1.5) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout):
            return True
    except Exception:  # noqa: BLE001 — any failure means "not reachable"
        return False


def resolve_provider(default_model: str = "meta-llama-3.1-8b-instruct") -> object:
    """Return a real, working ``LLMProvider`` — LM Studio, OpenAI, Anthropic, or Ollama.

    Args:
        default_model: Model name to request from LM Studio if
            ``CRP_LMSTUDIO_MODEL`` is not set (JIT model loading will load it
            on first request if it is not already loaded).
    """
    lmstudio_url = os.environ.get("CRP_LMSTUDIO_URL", "http://localhost:1234/v1")
    if _reachable(lmstudio_url.rsplit("/v1", 1)[0] + "/v1/models"):
        from crp.providers.openai import OpenAIAdapter

        model = os.environ.get("CRP_LMSTUDIO_MODEL", default_model)
        print(f"[provider] LM Studio detected at {lmstudio_url} — using {model}")
        return OpenAIAdapter(model=model, base_url=lmstudio_url, api_key="lm-studio")

    if os.environ.get("OPENAI_API_KEY"):
        from crp.providers.openai import OpenAIAdapter

        model = os.environ.get("CRP_OPENAI_MODEL", "gpt-4o-mini")
        print(f"[provider] OPENAI_API_KEY detected — using {model}")
        return OpenAIAdapter(model=model)

    if os.environ.get("ANTHROPIC_API_KEY"):
        from crp.providers.anthropic import AnthropicAdapter

        model = os.environ.get("CRP_ANTHROPIC_MODEL", "claude-3-5-haiku-20241022")
        print(f"[provider] ANTHROPIC_API_KEY detected — using {model}")
        return AnthropicAdapter(model=model)

    ollama_url = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
    if _reachable(ollama_url + "/api/tags"):
        from crp.providers.ollama import OllamaAdapter

        model = os.environ.get("CRP_OLLAMA_MODEL", "llama3.1")
        print(f"[provider] Ollama detected at {ollama_url} — using {model}")
        return OllamaAdapter(model=model, base_url=ollama_url)

    raise RuntimeError(
        "No LLM available. This template runs against a real model — start one of:\n"
        "  - LM Studio (https://lmstudio.ai) and start its local server, or\n"
        "  - Ollama (`ollama serve`), or\n"
        "  - export OPENAI_API_KEY=... or ANTHROPIC_API_KEY=...\n"
        "Then re-run this script."
    )
