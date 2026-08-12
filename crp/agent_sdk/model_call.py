# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Provider-agnostic model-call adapter for the Agent SDK (CRP-SPEC-059 §5).

Reuses the existing positioned-loop adapter so that any CRP ``LLMProvider`` can
power an ``Agent``.
"""

from __future__ import annotations

from typing import Any

from crp.stl.positioned import provider_model_call

ModelCall = Any  # (prompt: str, schema: dict | None) -> str


def build_model_call(
    provider: Any,
    *,
    temperature: float = 0.2,
    max_tokens: int = 1024,
) -> ModelCall:
    """Return a ``model_call`` callable bound to ``provider``."""
    return provider_model_call(provider, temperature=temperature, max_tokens=max_tokens)
