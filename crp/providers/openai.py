# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""OpenAI adapter — GPT-4o, GPT-4, GPT-3.5-turbo, o1/o3 families (§6.1).

Requires ``openai>=1.0`` (``pip install crprotocol[full]``).

Usage::

    from crp.providers.openai import OpenAIAdapter

    provider = OpenAIAdapter(model="gpt-4o")
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
from typing import Any

from crp.providers.base import LLMProvider

logger = logging.getLogger("crp.providers.openai")

# Model → context window (tokens).  Updated as of 2025-Q2.
# Primary table: exact OpenAI model names.
_MODEL_CONTEXT: dict[str, int] = {
    "gpt-4o": 128_000,
    "gpt-4o-mini": 128_000,
    "gpt-4-turbo": 128_000,
    "gpt-4": 8_192,
    "gpt-3.5-turbo": 16_385,
    "o1": 200_000,
    "o1-mini": 128_000,
    "o1-preview": 128_000,
    "o3": 200_000,
    "o3-mini": 200_000,
    "o4-mini": 200_000,
}

# Model → max output tokens (hard cap set by OpenAI).
_MODEL_MAX_OUTPUT: dict[str, int] = {
    "gpt-4o": 16_384,
    "gpt-4o-mini": 16_384,
    "gpt-4-turbo": 4_096,
    "gpt-4": 8_192,
    "gpt-3.5-turbo": 4_096,
    "o1": 100_000,
    "o1-mini": 65_536,
    "o1-preview": 32_768,
    "o3": 100_000,
    "o3-mini": 100_000,
    "o4-mini": 100_000,
}

# ── Model family table (prefix-matched) ─────────────────────────────
# Used when the model name is NOT in the primary OpenAI table.
# This covers open-source models served via OpenAI-compatible APIs
# (LM Studio, vLLM, llama.cpp server, Ollama OpenAI compat, TGI, etc.).
# Ordered longest-prefix-first to ensure specific matches win.
_MODEL_FAMILY_CONTEXT: list[tuple[str, int, int]] = [
    # (prefix, context_window, max_output_tokens)
    # Qwen family
    ("qwen3",           40_960,  8_192),
    ("qwen2.5",        128_000,  8_192),
    ("qwen2",          128_000,  8_192),
    ("qwen",            32_768,  4_096),
    # LLaMA family
    ("llama-3.3",      128_000,  4_096),
    ("llama-3.2",      128_000,  4_096),
    ("llama-3.1",      128_000,  4_096),
    ("llama3.3",       128_000,  4_096),
    ("llama3.2",       128_000,  4_096),
    ("llama3.1",       128_000,  4_096),
    ("llama-3",          8_192,  4_096),
    ("llama3",           8_192,  4_096),
    ("llama-2",          4_096,  4_096),
    ("llama2",           4_096,  4_096),
    ("codellama",       16_384,  4_096),
    # Gemma family
    ("gemma-3-27b",    128_000,  8_192),
    ("gemma-3",         32_768,  4_096),  # Smaller gemma-3 variants
    ("gemma3",         128_000,  8_192),
    ("gemma-2",          8_192,  4_096),
    ("gemma2",           8_192,  4_096),
    ("gemma",            8_192,  4_096),
    # Mistral family
    ("mistral-large",  128_000,  8_192),
    ("mistral-medium",  32_768,  4_096),
    ("mistral-small",   32_768,  4_096),
    ("mixtral",         32_768,  4_096),
    ("mistral",         32_768,  4_096),
    # Phi family
    ("phi-4",           16_384,  4_096),
    ("phi4",            16_384,  4_096),
    ("phi-3",          128_000,  4_096),
    ("phi3",           128_000,  4_096),
    # DeepSeek family
    ("deepseek-r1",    128_000, 16_384),
    ("deepseek-v3",    128_000, 16_384),
    ("deepseek-v2",    128_000,  8_192),
    ("deepseek-coder", 128_000,  8_192),
    ("deepseek",       128_000,  8_192),
    # Command-R family
    ("command-r-plus", 128_000,  4_096),
    ("command-r",      128_000,  4_096),
    # RWKV family
    ("rwkv",           100_000,  4_096),
    # Yi family
    ("yi-",            200_000,  4_096),
    # InternLM family
    ("internlm",      256_000,  8_192),
    # Anthropic (when proxied through OpenAI-compat)
    ("claude-3.5",     200_000,  8_192),
    ("claude-3",       200_000,  4_096),
    ("claude",         200_000,  4_096),
    # Youtu (WASA native)
    ("youtu",          128_000, 16_384),
]


def _resolve_model_capabilities(
    model: str,
    base_url: str | None = None,
) -> tuple[int, int]:
    """Resolve context window and max output for any model.

    Strategy (4-layer precedence):
    1. Live server probe (if base_url set) — authoritative for local servers,
       since it reports the context ACTUALLY loaded, which is frequently
       smaller than a model family's advertised maximum (LM Studio in
       particular defaults to a conservative loaded context regardless of
       what the underlying model architecture supports). Probing first
       avoids sending prompts sized for a 128K family default into a model
       that is really only serving 4-8K, which otherwise surfaces as
       "context length exceeded" failures deep in a run.
    2. Exact match in primary OpenAI table
    3. Prefix match against model family table (open-source models)
    4. Conservative fallback (8_192, 4_096) — NOT 128K

    Returns (context_window, max_output_tokens).
    """
    # Layer 1: live server probe — trust what the server reports is actually
    # loaded over any static table (local/custom endpoints only).
    if base_url:
        probed = _probe_server_model_info(model, base_url)
        if probed:
            return probed

    # Layer 2: exact match (OpenAI models)
    if model in _MODEL_CONTEXT:
        return (_MODEL_CONTEXT[model], _MODEL_MAX_OUTPUT.get(model, 4_096))

    # Layer 3: prefix match against model families
    lower = model.lower()
    for prefix, ctx, max_out in _MODEL_FAMILY_CONTEXT:
        if lower.startswith(prefix):
            logger.info(
                "Model '%s' matched family '%s': ctx=%d, max_out=%d",
                model, prefix, ctx, max_out,
            )
            return (ctx, max_out)

    # Layer 4: conservative fallback — NOT 128K (that's dangerous for small models)
    logger.warning(
        "Model '%s' not in any known table. Using conservative defaults "
        "(ctx=8192, max_out=4096). Override with context_size= parameter "
        "or add model to _MODEL_FAMILY_CONTEXT.",
        model,
    )
    return (8_192, 4_096)


def _probe_server_model_info(
    model: str,
    base_url: str,
) -> tuple[int, int] | None:
    """Probe the server for model metadata.

    Tries (in order):
    1. GET /api/v0/models (LM Studio native) — reports the context ACTUALLY
       loaded for this model, not just its architecture's maximum.
    2. GET /v1/models/{model} — some servers include context_length
    3. GET /api/show (Ollama-compat) — includes modelfile with num_ctx
    """
    url = base_url.rstrip("/")
    # LM Studio's native API lives at the server root; base_url is typically
    # the OpenAI-compat "<root>/v1" path, so strip that suffix to reach it.
    root = url[:-3] if url.endswith("/v1") else url

    # Attempt 0: LM Studio native endpoint — the loaded_context_length field
    # is the ground truth for what the server will actually serve, which is
    # commonly SMALLER than the model family's advertised max_context_length
    # (LM Studio defaults new loads to a conservative context window unless
    # explicitly configured otherwise).
    try:
        req = urllib.request.Request(
            f"{root}/api/v0/models",
            headers={"Accept": "application/json"},
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
            for entry in data.get("data", []):
                if entry.get("id") != model:
                    continue
                ctx = entry.get("loaded_context_length") or entry.get("max_context_length")
                if ctx and isinstance(ctx, int) and ctx > 0:
                    max_out = min(ctx // 4, 16_384)
                    logger.info(
                        "LM Studio native probe found model '%s': ctx=%d, max_out=%d (state=%s)",
                        model, ctx, max_out, entry.get("state", "unknown"),
                    )
                    return (ctx, max_out)
    except Exception:
        logger.debug("LM Studio native probe /api/v0/models failed (expected for non-LM-Studio servers)")

    # Attempt 1: /v1/models/{model} (vLLM, TGI expose max_model_len here)
    try:
        req = urllib.request.Request(
            f"{url}/v1/models/{model}",
            headers={"Accept": "application/json"},
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
            ctx = (
                data.get("max_model_len")
                or data.get("context_length")
                or data.get("max_context_length")
            )
            if ctx and isinstance(ctx, int) and ctx > 0:
                max_out = data.get("max_output_tokens", min(ctx // 4, 16_384))
                logger.info(
                    "Server probe found model '%s': ctx=%d, max_out=%d",
                    model, ctx, max_out,
                )
                return (ctx, max_out)
    except Exception:
        logger.debug("Server probe /v1/models/%s failed (expected for non-vLLM servers)", model)

    # Attempt 2: Ollama-compatible /api/show
    try:
        req = urllib.request.Request(
            f"{url}/api/show",
            data=json.dumps({"name": model}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
            params = data.get("model_info", {})
            ctx = params.get("context_length") or params.get("num_ctx")
            if ctx and isinstance(ctx, int) and ctx > 0:
                max_out = min(ctx // 4, 16_384)
                logger.info(
                    "Ollama probe found model '%s': ctx=%d, max_out=%d",
                    model, ctx, max_out,
                )
                return (ctx, max_out)
    except Exception:
        logger.debug("Ollama probe /api/show failed for '%s' (expected for non-Ollama servers)", model)

    return None


def _require_openai():
    """Import openai with a friendly error."""
    try:
        import openai
        return openai
    except ImportError:
        raise ImportError(
            "OpenAI adapter requires the 'openai' package. "
            "Install with: pip install crprotocol[full]"
        ) from None


def _require_tiktoken():
    """Import tiktoken with a friendly error."""
    try:
        import tiktoken
        return tiktoken
    except ImportError:
        return None  # Fall back to heuristic


class OpenAIAdapter(LLMProvider):
    """OpenAI chat completions adapter.

    Works with OpenAI API and any OpenAI-compatible server (LM Studio,
    vLLM, llama.cpp server, Ollama OpenAI compat, TGI, etc.).

    Model capabilities are auto-discovered via 3-layer resolution:
    1. Exact match against known OpenAI models
    2. Prefix match against 50+ open-source model families
    3. Server-side probing (for vLLM, Ollama-compat endpoints)
    4. Conservative fallback (8K context) — safe for unknown models

    Args:
        model:        Model name (e.g. "gpt-4o", "qwen3-4b", "llama3.1").
        api_key:      API key.  Defaults to ``OPENAI_API_KEY`` env var.
        base_url:     Override API base URL (for LM Studio, vLLM, etc.).
        context_size: Override auto-discovered context window (tokens).
        max_tokens:   Override auto-discovered max output tokens per request.
        timeout:      HTTP timeout in seconds (default: 120).
    """

    def __init__(
        self,
        model: str = "gpt-4o",
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        context_size: int | None = None,
        max_tokens: int | None = None,
        timeout: float = 120.0,
    ) -> None:
        openai = _require_openai()

        self._model = model

        # ── Auto-discover model capabilities (3-layer) ──────────
        # User-explicit overrides always win.
        resolved_ctx, resolved_max = _resolve_model_capabilities(model, base_url)
        self._context_size = context_size or resolved_ctx
        self._max_tokens = max_tokens or resolved_max

        # Build the client.
        # Custom/local endpoints (LM Studio, llama.cpp, Ollama, vLLM without
        # auth) do not require a real API key.  When base_url is set, accept
        # empty/None keys and pass a placeholder so the OpenAI SDK is happy.
        key = api_key or os.environ.get("OPENAI_API_KEY")
        if not key:
            if base_url:
                key = "not-needed"
            else:
                raise ValueError(
                    "No API key provided. Pass api_key= or set OPENAI_API_KEY."
                )
        kwargs: dict[str, Any] = {"api_key": key, "timeout": timeout}
        if base_url:
            kwargs["base_url"] = base_url
        self._client = openai.OpenAI(**kwargs)

        # Tokenizer (optional — tiktoken for accurate counts)
        tiktoken = _require_tiktoken()
        self._encoding = None
        if tiktoken:
            try:
                self._encoding = tiktoken.encoding_for_model(model)
            except KeyError:
                self._encoding = tiktoken.get_encoding("cl100k_base")

        logger.info(
            "OpenAIAdapter initialized: model=%s, ctx=%d, max_out=%d (auto-discovered=%s)",
            model, self._context_size, self._max_tokens,
            "no" if context_size or max_tokens else "yes",
        )

        # Reasoning/thinking content from the last generate_chat() call.
        # Set after every call; None if no reasoning was present.
        self.last_reasoning_content: str | None = None

    # -- LLMProvider interface --------------------------------------------

    # Retry config: 3 attempts, exponential backoff with jitter
    _MAX_RETRIES = 4
    _BASE_DELAY = 2.0  # seconds (generous for local inference servers)

    @staticmethod
    def _is_retryable(exc: Exception) -> bool:
        """Check if an exception is transient and worth retrying."""
        exc_type = type(exc).__name__
        # Rate limit (429) or server error (500/502/503)
        if hasattr(exc, "status_code"):
            return exc.status_code in (429, 500, 502, 503)
        # openai.RateLimitError, openai.APIConnectionError, etc.
        if exc_type in ("RateLimitError", "APIConnectionError", "APITimeoutError",
                        "InternalServerError", "APIStatusError"):
            return True
        # Connection-level transients (includes Channel Error from LM Studio)
        if isinstance(exc, (ConnectionError, TimeoutError, OSError)):
            return True
        # Catch-all: retry anything with "channel", "connection", "reset" in message
        exc_msg = str(exc).lower()
        if any(kw in exc_msg for kw in ("channel", "connection", "reset", "closed")):
            return True
        return False

    def generate_chat(
        self, messages: list[dict[str, str]], **kwargs: Any
    ) -> tuple[str, str]:
        """Call OpenAI chat completions API with retry on transient failures.

        Handles "thinking" models (Qwen3, DeepSeek-R1, o1, etc.) that
        split output into reasoning_content + content fields. CRP
        extracts the final content and preserves the full reasoning
        for downstream extraction.

        Returns (output_text, finish_reason).
        """
        params: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "max_tokens": kwargs.pop("max_tokens", self._max_tokens),
        }
        params.update(kwargs)

        last_exc: Exception | None = None
        for attempt in range(self._MAX_RETRIES):
            try:
                response = self._client.chat.completions.create(**params)
                choice = response.choices[0]
                text = choice.message.content or ""
                reason = choice.finish_reason or "stop"

                # ── Handle thinking models ──────────────────────
                # Models like Qwen3, DeepSeek-R1, o1 put reasoning
                # in a separate field. If content is empty but
                # reasoning exists, the model spent all tokens on
                # thinking and didn't produce final output.
                reasoning = getattr(choice.message, "reasoning_content", None)
                self.last_reasoning_content = reasoning or None
                if not text and reasoning:
                    # Model exhausted budget on reasoning — no final
                    # content produced.  Return empty output with
                    # finish_reason="length" so the continuation engine
                    # knows the budget was exhausted (not that the model
                    # finished).  The orchestrator will skip extraction
                    # for this window and continue to the next one.
                    # Reasoning is preserved for inspection but NOT used
                    # as output — it would pollute the document map.
                    text = ""
                    reason = "length"
                    logger.info(
                        "Thinking model: all tokens spent on reasoning "
                        "(%d chars), no content produced. Returning "
                        "finish_reason=length so continuation proceeds.",
                        len(reasoning),
                    )
                elif text and reasoning:
                    # Both present — model completed reasoning AND produced
                    # final content. CRP gets the clean content. Reasoning
                    # is discarded (it's internal chain-of-thought).
                    logger.debug(
                        "Thinking model: reasoning=%d chars, content=%d chars",
                        len(reasoning), len(text),
                    )

                # Map OpenAI finish reasons to CRP convention
                if reason == "length":
                    pass  # Already correct — physical wall
                elif reason in ("stop", "end_turn"):
                    reason = "stop"
                else:
                    reason = "stop"  # content_filter, tool_calls, etc.

                return (text, reason)
            except Exception as exc:
                last_exc = exc
                if attempt < self._MAX_RETRIES - 1 and self._is_retryable(exc):
                    delay = self._BASE_DELAY * (2 ** attempt) + random.uniform(0, 0.5)
                    logger.warning(
                        "OpenAI transient error (attempt %d/%d), retrying in %.1fs: %s",
                        attempt + 1, self._MAX_RETRIES, delay, type(exc).__name__,
                    )
                    time.sleep(delay)
                else:
                    logger.error("OpenAI API error: %s", type(exc).__name__)
                    return ("", "error")

        logger.error("OpenAI API failed after %d retries: %s", self._MAX_RETRIES, type(last_exc).__name__)
        return ("", "error")

    def count_tokens(self, text: str) -> int:
        """Count tokens using tiktoken (exact) or fallback heuristic."""
        if self._encoding is not None:
            return len(self._encoding.encode(text))
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

    # Thinking model prefixes — models that produce reasoning_content
    _THINKING_PREFIXES = ("qwen3", "deepseek-r1", "o1", "o3", "o4")

    @property
    def is_thinking_model(self) -> bool:
        """Detect if the current model is a thinking/reasoning model."""
        name = self._model.lower()
        return any(name.startswith(p) for p in self._THINKING_PREFIXES)

    def cost_per_1k_tokens(self) -> tuple[float, float]:
        """OpenAI pricing per 1K tokens (USD) — updated 2025-Q2."""
        pricing = {
            "gpt-4o":         (0.0025, 0.010),
            "gpt-4o-mini":    (0.00015, 0.0006),
            "gpt-4-turbo":    (0.010, 0.030),
            "gpt-4":          (0.030, 0.060),
            "gpt-3.5-turbo":  (0.0005, 0.0015),
            "o1":             (0.015, 0.060),
            "o1-mini":        (0.003, 0.012),
            "o3":             (0.015, 0.060),
            "o3-mini":        (0.0011, 0.0044),
            "o4-mini":        (0.0011, 0.0044),
        }
        return pricing.get(self._model, (0.0, 0.0))

    # ── Tool-mediated dispatch (§20) ──────────────────────────────────

    def supports_tools(self) -> bool:
        """OpenAI and compatible servers support function/tool calling."""
        return True

    def generate_chat_with_tools(
        self,
        messages: list[dict[str, object]],
        tools: list[dict[str, object]],
        **kwargs: object,
    ) -> tuple[str, str, list[dict[str, object]] | None, dict[str, object] | None]:
        """Generate with OpenAI tool/function calling.

        Returns (text, finish_reason, tool_calls, raw_assistant_message).
        When the model wants to call tools, finish_reason="tool_calls" and
        the tool_calls list contains structured call requests. The
        raw_assistant_message is the full message dict for appending to
        conversation history (required by the OpenAI tool protocol).
        """
        params: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "max_tokens": kwargs.pop("max_tokens", self._max_tokens),
            "tools": tools,
            "tool_choice": kwargs.pop("tool_choice", "auto"),
        }
        params.update(kwargs)

        last_exc: Exception | None = None
        for attempt in range(self._MAX_RETRIES):
            try:
                response = self._client.chat.completions.create(**params)
                choice = response.choices[0]
                text = choice.message.content or ""
                reason = choice.finish_reason or "stop"

                # Extract tool calls if present
                raw_tool_calls = choice.message.tool_calls
                if raw_tool_calls:
                    tool_calls_out: list[dict[str, object]] = []
                    for tc in raw_tool_calls:
                        # Parse arguments (may be JSON string)
                        try:
                            args = json.loads(tc.function.arguments) if isinstance(tc.function.arguments, str) else tc.function.arguments
                        except (json.JSONDecodeError, TypeError):
                            args = {"raw": tc.function.arguments}

                        tool_calls_out.append({
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": args,
                            },
                        })

                    # Build raw assistant message for conversation history
                    raw_msg: dict[str, Any] = {
                        "role": "assistant",
                        "content": text or None,
                        "tool_calls": [
                            {
                                "id": tc.id,
                                "type": "function",
                                "function": {
                                    "name": tc.function.name,
                                    "arguments": tc.function.arguments if isinstance(tc.function.arguments, str) else json.dumps(tc.function.arguments),
                                },
                            }
                            for tc in raw_tool_calls
                        ],
                    }

                    logger.info(
                        "Tool calls requested: %d calls [%s]",
                        len(tool_calls_out),
                        ", ".join(tc["function"]["name"] for tc in tool_calls_out),
                    )
                    return (text, "tool_calls", tool_calls_out, raw_msg)

                # No tool calls — normal completion
                # Handle thinking models (same as generate_chat)
                reasoning = getattr(choice.message, "reasoning_content", None)
                self.last_reasoning_content = reasoning or None
                if not text and reasoning:
                    text = ""
                    reason = "length"

                if reason == "length":
                    pass
                elif reason in ("stop", "end_turn"):
                    reason = "stop"
                else:
                    reason = "stop"

                return (text, reason, None, None)

            except Exception as exc:
                last_exc = exc
                if attempt < self._MAX_RETRIES - 1 and self._is_retryable(exc):
                    delay = self._BASE_DELAY * (2 ** attempt) + random.uniform(0, 0.5)
                    logger.warning(
                        "OpenAI tool call transient error (attempt %d/%d), retrying in %.1fs: %s",
                        attempt + 1, self._MAX_RETRIES, delay, exc,
                    )
                    time.sleep(delay)
                else:
                    logger.error("OpenAI tool call API error: %s", exc)
                    return ("", "error", None, None)

        logger.error("OpenAI tool call failed after %d retries: %s", self._MAX_RETRIES, last_exc)
        return ("", "error", None, None)

    def generate_chat_stream(
        self,
        messages: list[dict[str, str]],
        **kwargs: object,
    ):
        """Stream token chunks from OpenAI.

        Yields individual token deltas. Return value is finish_reason.
        """
        from collections.abc import Generator

        params: dict[str, object] = {
            "model": self._model,
            "messages": messages,
            "max_tokens": kwargs.pop("max_tokens", self._max_tokens) if "max_tokens" in kwargs else self._max_tokens,
            "stream": True,
        }
        params.update(kwargs)

        finish_reason = "stop"
        try:
            stream = self._client.chat.completions.create(**params)
            for chunk in stream:
                if chunk.choices:
                    delta = chunk.choices[0].delta
                    if delta and delta.content:
                        yield delta.content
                    fr = chunk.choices[0].finish_reason
                    if fr:
                        finish_reason = "length" if fr == "length" else "stop"
        except Exception as exc:
            logger.error("OpenAI streaming error: %s", exc)
            finish_reason = "error"

        return finish_reason
