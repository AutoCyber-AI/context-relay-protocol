# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Ollama adapter — local model inference via Ollama REST API (§6.1).

Requires a running Ollama instance (``ollama serve``).

Usage::

    from crp.providers.ollama import OllamaAdapter

    provider = OllamaAdapter(model="llama3.1")
    output, reason = provider.generate_chat([
        {"role": "system", "content": "You are helpful."},
        {"role": "user", "content": "Hello!"},
    ])
"""

from __future__ import annotations

import json
import logging
import os
import random
import time
import urllib.request
import urllib.error
import uuid
from typing import Any

from crp.providers.base import LLMProvider

logger = logging.getLogger("crp.providers.ollama")

# Model family → context window (tokens).
# Ollama defaults to 2048; most models support much more with num_ctx.
_MODEL_CONTEXT: dict[str, int] = {
    "llama3.1": 128_000,
    "llama3.2": 128_000,
    "llama3.3": 128_000,
    "llama3": 8_192,
    "llama2": 4_096,
    "mistral": 32_768,
    "mixtral": 32_768,
    "gemma2": 8_192,
    "gemma3": 128_000,
    "qwen3": 40_960,
    "qwen2.5": 128_000,
    "qwen2": 128_000,
    "qwen": 32_768,
    "phi3": 128_000,
    "phi4": 16_384,
    "deepseek-r1": 128_000,
    "deepseek-v3": 128_000,
    "deepseek-coder": 128_000,
    "command-r": 128_000,
    "codellama": 16_384,
    "yi": 200_000,
    "internlm": 256_000,
    "rwkv": 100_000,
    "youtu": 128_000,
}


def _resolve_context(model: str, base_url: str | None = None) -> int:
    """Resolve context window for a model.

    Strategy (3-layer):
    1. Prefix match against known families
    2. Server probe via /api/show (Ollama exposes model metadata)
    3. Conservative fallback (4_096) — safe for unknown models
    """
    # Layer 1: prefix match
    for prefix, ctx in _MODEL_CONTEXT.items():
        if model.startswith(prefix):
            return ctx

    # Layer 2: Ollama /api/show probe
    if base_url:
        try:
            import json
            req = urllib.request.Request(
                f"{base_url.rstrip('/')}/api/show",
                data=json.dumps({"name": model}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read())
                params = data.get("model_info", {})
                ctx = params.get("context_length") or params.get("num_ctx")
                if ctx and isinstance(ctx, int) and ctx > 0:
                    logger.info("Ollama probe: model '%s' → ctx=%d", model, ctx)
                    return ctx
        except Exception:
            pass

    logger.warning(
        "Model '%s' not in any known table. Using conservative default (ctx=4096). "
        "Override with context_size= parameter.",
        model,
    )
    return 4_096  # Conservative default


class OllamaAdapter(LLMProvider):
    """Ollama REST API adapter for local model inference.

    Args:
        model:        Model name (e.g. "llama3.1", "mistral", "gemma2").
        base_url:     Ollama API base URL.  Defaults to ``OLLAMA_HOST``
                      env var or ``http://localhost:11434``.
        context_size: Override context window size (tokens).
        max_tokens:   Max output tokens per request (default: 2048).
        timeout:      HTTP timeout in seconds (default: 300 — local
                      models can be slow on CPU).
    """

    def __init__(
        self,
        model: str = "llama3.1",
        *,
        base_url: str | None = None,
        context_size: int | None = None,
        max_tokens: int = 2_048,
        timeout: float = 300.0,
    ) -> None:
        self._model = model
        self._base_url = (
            base_url
            or os.environ.get("OLLAMA_HOST")
            or "http://localhost:11434"
        ).rstrip("/")
        self._context_size = context_size or _resolve_context(model, self._base_url)
        self._max_tokens = max_tokens
        self._timeout = timeout

        # Connection pooling: reuse a persistent opener with keep-alive
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPHandler(),
            urllib.request.HTTPSHandler(),
        )

        logger.debug(
            "OllamaAdapter initialized: model=%s, url=%s, ctx=%d",
            model, self._base_url, self._context_size,
        )

    # -- LLMProvider interface --------------------------------------------

    # Retry config: 4 attempts with exponential backoff + jitter
    _MAX_RETRIES = 4
    _BASE_DELAY = 2.0

    @staticmethod
    def _is_retryable(exc: Exception) -> bool:
        """Check if an exception is transient and worth retrying."""
        if isinstance(exc, (ConnectionError, TimeoutError, OSError)):
            return True
        if isinstance(exc, urllib.error.URLError):
            return True
        exc_msg = str(exc).lower()
        return any(kw in exc_msg for kw in ("connection", "reset", "refused", "timeout"))

    def generate_chat(
        self, messages: list[dict[str, str]], **kwargs: Any
    ) -> tuple[str, str]:
        """Call Ollama /api/chat endpoint with retry on transient failures.

        Returns (output_text, finish_reason).
        """
        payload = {
            "model": self._model,
            "messages": messages,
            "stream": False,
            "options": {
                "num_predict": kwargs.pop("max_tokens", self._max_tokens),
                "num_ctx": self._context_size,
            },
        }

        url = f"{self._base_url}/api/chat"
        data = json.dumps(payload).encode("utf-8")

        last_exc: Exception | None = None
        for attempt in range(self._MAX_RETRIES):
            req = urllib.request.Request(
                url,
                data=data,
                headers={
                    "Content-Type": "application/json",
                    "Connection": "keep-alive",
                },
                method="POST",
            )

            try:
                with self._opener.open(req, timeout=self._timeout) as resp:
                    body = json.loads(resp.read())

                text = body.get("message", {}).get("content", "")
                done = body.get("done", True)
                done_reason = body.get("done_reason", "stop")

                if done_reason == "length" or not done:
                    finish_reason = "length"
                else:
                    finish_reason = "stop"

                return (text, finish_reason)

            except Exception as exc:
                last_exc = exc
                if attempt < self._MAX_RETRIES - 1 and self._is_retryable(exc):
                    delay = self._BASE_DELAY * (2 ** attempt) + random.uniform(0, 0.5)
                    logger.warning(
                        "Ollama request failed (attempt %d/%d), retrying in %.1fs: %s",
                        attempt + 1, self._MAX_RETRIES, delay, exc,
                    )
                    time.sleep(delay)
                    continue
                logger.error("Ollama API error (non-retryable): %s", exc)
                return ("", "error")

        logger.error("Ollama API failed after %d retries: %s", self._MAX_RETRIES, last_exc)
        return ("", "error")

    def count_tokens(self, text: str) -> int:
        """Estimate token count (Ollama doesn't expose tokenizer directly).

        Uses a conservative ~3.5 chars/token estimate for most models.
        For exact counts, use the LlamaCppAdapter with model_path instead.
        """
        return max(1, len(text.encode("utf-8")) * 10 // 35)

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

    # ── Tool-mediated dispatch (§20) ──────────────────────────────────

    def supports_tools(self) -> bool:
        """Ollama supports OpenAI-compatible tool calling from 0.3.0+.

        Actual availability depends on the model (e.g. llama3.1, qwen2.5,
        mistral). CRP advertises support here and lets the server fail
        gracefully if the loaded model is not tool-capable.
        """
        return True

    def generate_chat_with_tools(
        self,
        messages: list[dict[str, object]],
        tools: list[dict[str, object]],
        **kwargs: object,
    ) -> tuple[str, str, list[dict[str, object]] | None, dict[str, object] | None]:
        """Generate with Ollama tool/function calling.

        Returns ``(text, finish_reason, tool_calls, raw_assistant_message)``.
        Finish reason is ``"tool_calls"`` when the model emits tool calls.
        """
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "stream": False,
            "tools": tools,
            "options": {
                "num_predict": kwargs.pop("max_tokens", self._max_tokens),
                "num_ctx": self._context_size,
            },
        }
        # Ollama accepts "auto" / "none" / {"type": "function", "function": {"name": ...}}
        tool_choice = kwargs.pop("tool_choice", "auto")
        if tool_choice is not None:
            payload["tool_choice"] = tool_choice
        payload.update(kwargs)

        url = f"{self._base_url}/api/chat"
        data = json.dumps(payload).encode("utf-8")

        last_exc: Exception | None = None
        for attempt in range(self._MAX_RETRIES):
            req = urllib.request.Request(
                url,
                data=data,
                headers={
                    "Content-Type": "application/json",
                    "Connection": "keep-alive",
                },
                method="POST",
            )

            try:
                with self._opener.open(req, timeout=self._timeout) as resp:
                    body = json.loads(resp.read())

                message = body.get("message", {}) or {}
                text = message.get("content", "") or ""
                raw_tool_calls = message.get("tool_calls")
                done_reason = body.get("done_reason", "stop")

                if raw_tool_calls:
                    tool_calls_out: list[dict[str, object]] = []
                    for tc in raw_tool_calls:
                        func = tc.get("function", {}) or {}
                        args_raw = func.get("arguments")
                        try:
                            args = json.loads(args_raw) if isinstance(args_raw, str) else args_raw
                        except (json.JSONDecodeError, TypeError):
                            args = {"raw": args_raw}
                        tool_calls_out.append({
                            "id": tc.get("id") or f"call_{uuid.uuid4().hex[:16]}",
                            "type": tc.get("type", "function"),
                            "function": {
                                "name": func.get("name", ""),
                                "arguments": args,
                            },
                        })

                    raw_msg: dict[str, Any] = {
                        "role": "assistant",
                        "content": text or None,
                        "tool_calls": [
                            {
                                "id": tc["id"],
                                "type": tc["type"],
                                "function": {
                                    "name": tc["function"]["name"],
                                    "arguments": json.dumps(tc["function"]["arguments"]),
                                },
                            }
                            for tc in tool_calls_out
                        ],
                    }
                    logger.info(
                        "Ollama tool calls requested: %d calls [%s]",
                        len(tool_calls_out),
                        ", ".join(tc["function"]["name"] for tc in tool_calls_out),
                    )
                    return (text, "tool_calls", tool_calls_out, raw_msg)

                if done_reason == "length" or not body.get("done", True):
                    finish_reason = "length"
                else:
                    finish_reason = "stop"
                return (text, finish_reason, None, None)

            except Exception as exc:
                last_exc = exc
                if attempt < self._MAX_RETRIES - 1 and self._is_retryable(exc):
                    delay = self._BASE_DELAY * (2 ** attempt) + random.uniform(0, 0.5)
                    logger.warning(
                        "Ollama tool-call request failed (attempt %d/%d), retrying in %.1fs: %s",
                        attempt + 1, self._MAX_RETRIES, delay, exc,
                    )
                    time.sleep(delay)
                    continue
                logger.error("Ollama tool-call API error (non-retryable): %s", exc)
                return ("", "error", None, None)

        logger.error("Ollama tool-call API failed after %d retries: %s", self._MAX_RETRIES, last_exc)
        return ("", "error", None, None)
