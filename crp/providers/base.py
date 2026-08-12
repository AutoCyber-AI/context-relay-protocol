# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""LLMProvider abstract base class — §6.1; CRP-SPEC-008.

Every provider adapter MUST implement ``generate_chat``, ``count_tokens``,
and ``context_window_size``. The protocol uses these three to compute
window budgets and dispatch tasks.

Relevant specifications:
  - CRP specification §6.1: Provider interface
  - CRP-SPEC-008: Dispatch & Provider Adaptation
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Generator


class LLMProvider(ABC):
    """Abstract interface for LLM backends.

    Implementations: OpenAIAdapter, AnthropicAdapter, LlamaCppAdapter, CustomProvider.

    Subclasses must implement the three core abstract methods:
    ``generate_chat``, ``count_tokens``, and ``context_window_size``.  The
    remaining methods provide optional metadata, cost estimates, and tool or
    streaming support.
    """

    @abstractmethod
    def generate_chat(
        self, messages: list[dict[str, str]], **kwargs: object
    ) -> tuple[str, str]:
        """Generate text completion from a message array.

        Args:
            messages: List of chat messages, e.g.
                ``[{"role": "system", "content": "..."}, ...]``.
            **kwargs: Provider-specific overrides (max_tokens, temperature, etc.)

        Returns:
            ``(output_text, finish_reason)`` where ``finish_reason`` is one of:
              - ``"length"``  — model hit generation reserve limit (physical wall)
              - ``"stop"``    — model produced natural EOS
              - ``"error"``   — provider returned an error
        """

    @abstractmethod
    def count_tokens(self, text: str) -> int:
        """Count tokens in *text* using this provider's exact tokenizer.

        MUST return accurate per-model counts — no estimates.

        Args:
            text: Text to tokenise.

        Returns:
            Number of tokens in ``text``.
        """

    @abstractmethod
    def context_window_size(self) -> int:
        """Return the model's physical context window size in tokens.

        E.g. 128_000 for Claude 3 Opus, 8_192 for GPT-3.5.

        Returns:
            Context window size in tokens.
        """

    @property
    def max_output_tokens(self) -> int | None:
        """Optional provider-reported max output tokens.

        Returns:
            Maximum output tokens, or None if not known.
        """
        return None

    @property
    def model_name(self) -> str:
        """Human-readable model identifier for diagnostics.

        Returns:
            Class name by default; subclasses may override with a specific
            model identifier.
        """
        return self.__class__.__name__

    @property
    def is_thinking_model(self) -> bool:
        """Return True if the model produces reasoning_content alongside output.

        Thinking models (qwen3, deepseek-r1, o1, etc.) spend a significant
        portion of tokens on internal reasoning, requiring a larger generation
        reserve to avoid starving the final content output.

        Returns:
            True when the provider represents a thinking model.
        """
        return False

    def cost_per_1k_tokens(self) -> tuple[float, float]:
        """Return (input_cost_per_1k, output_cost_per_1k) in USD.

        Returns:
            ``(input_cost, output_cost)`` per 1,000 tokens.  Defaults to
            ``(0.0, 0.0)`` for local models or unknown pricing.
        """
        return (0.0, 0.0)

    # ── Tool-mediated dispatch (§20) ──────────────────────────────────

    def supports_tools(self) -> bool:
        """Return True if this provider supports function/tool calling.

        Override in subclasses that implement ``generate_chat_with_tools()``.
        The orchestrator uses this to decide between push (envelope) and
        pull (tool-mediated) context relay.

        Returns:
            True when tool-mediated dispatch is supported.
        """
        return False

    def generate_chat_with_tools(
        self,
        messages: list[dict[str, object]],
        tools: list[dict[str, object]],
        **kwargs: object,
    ) -> tuple[str, str, list[dict[str, object]] | None, dict[str, object] | None]:
        """Generate with tool/function calling support.

        Args:
            messages: Chat messages (may include tool role messages).
            tools: Tool definitions in OpenAI-compatible format.
            **kwargs: Provider-specific overrides.

        Returns:
            ``(output_text, finish_reason, tool_calls, raw_assistant_message)``
            where:
            - ``output_text``: Generated text content (may be empty if tool_calls)
            - ``finish_reason``: "stop", "length", "tool_calls", or "error"
            - ``tool_calls``: List of tool call dicts if finish_reason=="tool_calls"
            - ``raw_assistant_message``: The full assistant message dict (for
              appending to conversation history in the tool loop)

        Raises:
            NotImplementedError: By default; subclasses must override this
                method when ``supports_tools()`` returns True.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support tool calling. "
            "Override supports_tools() and generate_chat_with_tools()."
        )

    def generate_chat_stream(
        self,
        messages: list[dict[str, str]],
        **kwargs: object,
    ) -> Generator[str, None, str]:
        """Stream token chunks from the LLM.

        Yields individual token chunks as strings.
        The return value (accessible via ``StopIteration.value``) is the
        finish_reason ("stop" or "length").

        Default implementation falls back to ``generate_chat()`` and yields
        the full output as a single chunk. Override in subclasses for
        real streaming.

        Args:
            messages: Chat messages.
            **kwargs: Provider-specific overrides.

        Yields:
            Token chunks as strings.

        Returns:
            The finish reason string.
        """
        output, finish_reason = self.generate_chat(messages, **kwargs)
        yield output
        return finish_reason
