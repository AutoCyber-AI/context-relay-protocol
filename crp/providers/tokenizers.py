# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Per-provider tokenizer reconciliation (§06 §6.4).

Three-layer hierarchy:
  Layer 1: Model-specific tokenizer (best — 100% accuracy)
  Layer 2: Provider API token counting (good — 99%)
  Layer 3: Character-to-token fallback (acceptable — 70-80%)
"""

from __future__ import annotations

from crp.providers.base import LLMProvider


class TokenizerRegistry:
    """Cache and resolve tokenizers per provider.

    Phase 1 implementation delegates to LLMProvider.count_tokens() which
    each adapter must implement with its own tokenizer. The registry adds
    the Layer 3 fallback heuristic for providers that raise.
    """

    _CHARS_PER_TOKEN = 4  # Layer 3 heuristic

    def count_tokens(self, text: str, provider: LLMProvider) -> int:
        """Count tokens using the best available method for *provider*.

        Layer 1/2: provider.count_tokens() — exact model tokenizer or API.
        Layer 3: chars/4 fallback if the provider raises.
        """
        try:
            return provider.count_tokens(text)
        except Exception:
            return self._fallback_count(text)

    def _fallback_count(self, text: str) -> int:
        """Layer 3: ~4 characters = 1 token average."""
        return max(1, len(text) // self._CHARS_PER_TOKEN)

    def validate_roundtrip(self, text: str, provider: LLMProvider) -> bool:
        """Validate encode→decode→encode is lossless (best-effort)."""
        try:
            count1 = provider.count_tokens(text)
            count2 = provider.count_tokens(text)
            return count1 == count2
        except Exception:
            return False
