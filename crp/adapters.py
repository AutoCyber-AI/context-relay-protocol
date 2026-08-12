# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Compatibility alias — ``from crp.adapters import ...``

This module re-exports everything from :mod:`crp.providers` so that
documentation examples using ``crp.adapters`` work unchanged.

Canonical location is ``crp.providers``.
"""

from crp.providers import (  # noqa: F401
    AnthropicAdapter,
    BaseAdapter,
    CallableAdapter,
    CustomProvider,
    LlamaCppAdapter,
    LLMProvider,
    OllamaAdapter,
    OpenAIAdapter,
)

__all__ = [
    "LLMProvider",
    "BaseAdapter",
    "OpenAIAdapter",
    "AnthropicAdapter",
    "OllamaAdapter",
    "LlamaCppAdapter",
    "CustomProvider",
    "CallableAdapter",
]
