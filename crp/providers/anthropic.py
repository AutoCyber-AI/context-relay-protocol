# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Anthropic adapter — Claude 3/3.5/4 families (§6.1).

Requires ``anthropic>=0.25`` (``pip install crprotocol[full]``).

Usage::

    from crp.providers.anthropic import AnthropicAdapter

    provider = AnthropicAdapter(model="claude-sonnet-4-20250514")
    output, reason = provider.generate_chat([
        {"role": "system", "content": "You are helpful."},
        {"role": "user", "content": "Hello!"},
    ])
"""

from __future__ import annotations

import logging
import os
import random
import time
from typing import Any

from crp.providers.base import LLMProvider

logger = logging.getLogger("crp.providers.anthropic")

# Model → context window (tokens).  Updated as of 2025-Q2.
_MODEL_CONTEXT: dict[str, int] = {
    "claude-opus-4-20250514": 200_000,
    "claude-sonnet-4-20250514": 200_000,
    "claude-3-7-sonnet-20250219": 200_000,
    "claude-3-5-sonnet-20241022": 200_000,
    "claude-3-5-sonnet-20240620": 200_000,
    "claude-3-5-haiku-20241022": 200_000,
    "claude-3-opus-20240229": 200_000,
    "claude-3-sonnet-20240229": 200_000,
    "claude-3-haiku-20240307": 200_000,
}

# Model → max output tokens.
_MODEL_MAX_OUTPUT: dict[str, int] = {
    "claude-opus-4-20250514": 32_000,
    "claude-sonnet-4-20250514": 16_000,
    "claude-3-7-sonnet-20250219": 16_000,
    "claude-3-5-sonnet-20241022": 8_192,
    "claude-3-5-sonnet-20240620": 8_192,
    "claude-3-5-haiku-20241022": 8_192,
    "claude-3-opus-20240229": 4_096,
    "claude-3-sonnet-20240229": 4_096,
    "claude-3-haiku-20240307": 4_096,
}


def _require_anthropic():
    """Import anthropic with a friendly error."""
    try:
        import anthropic
        return anthropic
    except ImportError:
        raise ImportError(
            "Anthropic adapter requires the 'anthropic' package. "
            "Install with: pip install crprotocol[full]"
        ) from None


class AnthropicAdapter(LLMProvider):
    """Anthropic Claude chat adapter.

    Args:
        model:      Model name (e.g. "claude-sonnet-4-20250514").
        api_key:    API key.  Defaults to ``ANTHROPIC_API_KEY`` env var.
        max_tokens: Max output tokens per request (default: model limit).
        timeout:    HTTP timeout in seconds (default: 120).
    """

    def __init__(
        self,
        model: str = "claude-sonnet-4-20250514",
        *,
        api_key: str | None = None,
        max_tokens: int | None = None,
        timeout: float = 120.0,
    ) -> None:
        anthropic = _require_anthropic()

        self._model = model
        self._max_tokens = max_tokens or _MODEL_MAX_OUTPUT.get(model, 4_096)
        self._context_size = _MODEL_CONTEXT.get(model, 200_000)

        key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise ValueError(
                "No API key provided. Pass api_key= or set ANTHROPIC_API_KEY."
            )
        self._client = anthropic.Anthropic(
            api_key=key,
            timeout=timeout,
        )

        logger.debug(
            "AnthropicAdapter initialized: model=%s, ctx=%d",
            model, self._context_size,
        )

    # -- LLMProvider interface --------------------------------------------

    # Retry config: 3 attempts, exponential backoff with jitter
    _MAX_RETRIES = 3
    _BASE_DELAY = 1.0  # seconds

    @staticmethod
    def _is_retryable(exc: Exception) -> bool:
        """Check if an exception is transient and worth retrying."""
        exc_type = type(exc).__name__
        if hasattr(exc, "status_code"):
            return exc.status_code in (429, 500, 502, 503, 529)
        if exc_type in ("RateLimitError", "APIConnectionError", "APITimeoutError",
                        "OverloadedError", "InternalServerError"):
            return True
        if isinstance(exc, (ConnectionError, TimeoutError)):
            return True
        return False

    def generate_chat(
        self, messages: list[dict[str, str]], **kwargs: Any
    ) -> tuple[str, str]:
        """Call Anthropic Messages API with retry on transient failures.

        Anthropic uses a separate ``system`` parameter instead of a system
        message in the array, so we extract it automatically.

        Returns (output_text, finish_reason).
        """
        # Extract system message (Anthropic API uses separate param)
        system_text = ""
        chat_messages = []
        for msg in messages:
            if msg.get("role") == "system":
                system_text = msg.get("content", "")
            else:
                chat_messages.append(msg)

        # Ensure at least one user message
        if not chat_messages:
            chat_messages = [{"role": "user", "content": ""}]

        params: dict[str, Any] = {
            "model": self._model,
            "messages": chat_messages,
            "max_tokens": kwargs.pop("max_tokens", self._max_tokens),
        }
        if system_text:
            params["system"] = system_text

        last_exc: Exception | None = None
        for attempt in range(self._MAX_RETRIES):
            try:
                response = self._client.messages.create(**params)

                # Extract text from content blocks
                text_parts = []
                for block in response.content:
                    if hasattr(block, "text"):
                        text_parts.append(block.text)
                text = "".join(text_parts)

                # Map Anthropic stop reasons to CRP convention
                stop_reason = response.stop_reason or "end_turn"
                if stop_reason == "max_tokens":
                    finish_reason = "length"
                elif stop_reason in ("end_turn", "stop_sequence"):
                    finish_reason = "stop"
                else:
                    finish_reason = "stop"

                return (text, finish_reason)
            except Exception as exc:
                last_exc = exc
                if attempt < self._MAX_RETRIES - 1 and self._is_retryable(exc):
                    delay = self._BASE_DELAY * (2 ** attempt) + random.uniform(0, 0.5)
                    logger.warning(
                        "Anthropic transient error (attempt %d/%d), retrying in %.1fs: %s",
                        attempt + 1, self._MAX_RETRIES, delay, exc,
                    )
                    time.sleep(delay)
                else:
                    logger.error("Anthropic API error: %s", exc)
                    return ("", "error")

        logger.error("Anthropic API failed after %d retries: %s", self._MAX_RETRIES, last_exc)
        return ("", "error")

    def count_tokens(self, text: str) -> int:
        """Count tokens using Anthropic's tokenizer if available.

        Falls back to ~3.5 chars/token heuristic (Claude uses a modified
        BPE tokenizer similar to GPT-4's).
        """
        try:
            return self._client.count_tokens(text)
        except Exception:
            return max(1, len(text) // 4)

    def context_window_size(self) -> int:
        """Return the current context window count.
        
            Returns:
                ``int``.
        """
        return self._context_size

    @property
    def max_output_tokens(self) -> int | None:
        """Return the max output tokens."""
        return self._max_tokens

    @property
    def model_name(self) -> str:
        """Return the model name."""
        return self._model

    def cost_per_1k_tokens(self) -> tuple[float, float]:
        """Anthropic pricing per 1K tokens (USD) — updated 2025-Q2."""
        pricing = {
            "claude-opus-4-20250514":       (0.015, 0.075),
            "claude-sonnet-4-20250514":     (0.003, 0.015),
            "claude-3-5-sonnet-20241022":   (0.003, 0.015),
            "claude-3-5-haiku-20241022":    (0.0008, 0.004),
            "claude-3-opus-20240229":       (0.015, 0.075),
            "claude-3-haiku-20240307":      (0.00025, 0.00125),
        }
        return pricing.get(self._model, (0.0, 0.0))

    def generate_chat_stream(
        self,
        messages: list[dict[str, str]],
        **kwargs: object,
    ):
        """Stream token chunks from Anthropic.

        Yields individual text deltas. Return value is finish_reason.
        """
        # Extract system message
        system_text = ""
        chat_messages = []
        for msg in messages:
            if msg.get("role") == "system":
                system_text = msg.get("content", "")
            else:
                chat_messages.append(msg)
        if not chat_messages:
            chat_messages = [{"role": "user", "content": ""}]

        params: dict[str, object] = {
            "model": self._model,
            "messages": chat_messages,
            "max_tokens": kwargs.pop("max_tokens", self._max_tokens) if "max_tokens" in kwargs else self._max_tokens,
        }
        if system_text:
            params["system"] = system_text

        finish_reason = "stop"
        try:
            with self._client.messages.stream(**params) as stream:
                for text in stream.text_stream:
                    yield text
                response = stream.get_final_message()
                if response.stop_reason == "max_tokens":
                    finish_reason = "length"
        except Exception as exc:
            logger.error("Anthropic streaming error: %s", exc)
            finish_reason = "error"

        return finish_reason
