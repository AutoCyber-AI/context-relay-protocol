# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""CustomProvider — user-supplied LLM adapter (Axiom 6: Portability; CRP-SPEC-008).

Allows any LLM to be used with CRP if the user provides three callables:
  generate_fn(messages) → (output, finish_reason)
  count_tokens_fn(text) → int
  context_size → int

Relevant specifications:
  - CRP-SPEC-008: Dispatch & Provider Adaptation
  - Axiom 6: Portability
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from crp.providers.base import LLMProvider


class CustomProvider(LLMProvider):
    """User-supplied LLM backend.

    Example::

        provider = CustomProvider(
            generate_fn=my_generate,
            count_tokens_fn=my_tokenizer,
            context_size=8192,
        )

    Args:
        generate_fn: Callable accepting a message list and returning
            ``(output_text, finish_reason)``.
        count_tokens_fn: Callable returning the token count for a string.
        context_size: Model context window size in tokens.
        name: Human-readable provider name.
        max_output: Optional maximum output token count.
    """

    def __init__(
        self,
        generate_fn: Callable[[list[dict[str, str]]], tuple[str, str]],
        count_tokens_fn: Callable[[str], int],
        context_size: int,
        *,
        name: str = "custom",
        max_output: int | None = None,
    ) -> None:
        self._generate_fn = generate_fn
        self._count_tokens_fn = count_tokens_fn
        self._context_size = context_size
        self._name = name
        self._max_output = max_output

    def generate_chat(
        self, messages: list[dict[str, str]], **kwargs: Any
    ) -> tuple[str, str]:
        """Generate a completion using the user-supplied function.

        Args:
            messages: Chat messages.
            **kwargs: Ignored by this adapter; accepted for API compatibility.

        Returns:
            ``(output_text, finish_reason)`` from ``generate_fn``.
        """
        return self._generate_fn(messages)

    def count_tokens(self, text: str) -> int:
        """Count tokens using the user-supplied tokenizer.

        Args:
            text: Text to tokenise.

        Returns:
            Token count.
        """
        return self._count_tokens_fn(text)

    def context_window_size(self) -> int:
        """Return the configured context window size.

        Returns:
            Context window size in tokens.
        """
        return self._context_size

    @property
    def max_output_tokens(self) -> int | None:
        """Return the configured maximum output tokens, if any."""
        return self._max_output

    @property
    def model_name(self) -> str:
        """Return the configured provider name."""
        return self._name
