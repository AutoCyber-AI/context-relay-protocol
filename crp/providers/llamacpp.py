# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""llama.cpp adapter — local model inference via llama-cpp-python or HTTP (§6.1).

Supports two modes:
  1. **Python binding**: ``pip install llama-cpp-python`` (in-process inference).
  2. **HTTP server**: ``llama-server --model model.gguf --port 8080``
     (talks to llama.cpp's OpenAI-compatible endpoint).

Usage (Python binding)::

    from crp.providers.llamacpp import LlamaCppAdapter

    provider = LlamaCppAdapter(model_path="/models/llama3-8b.gguf")
    output, reason = provider.generate_chat([
        {"role": "user", "content": "Hello!"},
    ])

Usage (HTTP server)::

    provider = LlamaCppAdapter(server_url="http://localhost:8080")
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

logger = logging.getLogger("crp.providers.llamacpp")


class LlamaCppAdapter(LLMProvider):
    """llama.cpp adapter — local inference or HTTP server.

    Args:
        model_path:     Path to a GGUF model file (Python binding mode).
        server_url:     Base URL for llama.cpp's HTTP server (e.g. "http://localhost:8080").
                        If provided, *model_path* is ignored.
        context_size:   Context window size in tokens (default: 4096).
        max_tokens:     Max output tokens per generation (default: 2048).
        n_gpu_layers:   GPU layers for Python binding (default: -1 = all).
        n_threads:      CPU threads for Python binding (default: os.cpu_count()).
    """

    def __init__(
        self,
        *,
        model_path: str | None = None,
        server_url: str | None = None,
        context_size: int = 4_096,
        max_tokens: int = 2_048,
        n_gpu_layers: int = -1,
        n_threads: int | None = None,
    ) -> None:
        if not model_path and not server_url:
            raise ValueError(
                "LlamaCppAdapter requires either model_path (Python binding) "
                "or server_url (HTTP mode)."
            )

        self._context_size = context_size
        self._max_tokens = max_tokens
        self._server_url = server_url
        self._llama = None  # Lazy-loaded Python binding
        self._model_path = model_path
        self._n_gpu_layers = n_gpu_layers
        self._n_threads = n_threads or (os.cpu_count() or 4)

        if server_url:
            logger.debug("LlamaCppAdapter: HTTP mode → %s", server_url)
        else:
            logger.debug("LlamaCppAdapter: Python binding → %s", model_path)

    # -- lazy init --------------------------------------------------------

    def _ensure_model(self) -> Any:
        """Lazy-load the llama-cpp-python model on first use."""
        if self._llama is not None:
            return self._llama

        if self._server_url:
            return None  # HTTP mode — no local model

        try:
            from llama_cpp import Llama
        except ImportError:
            raise ImportError(
                "Python binding mode requires 'llama-cpp-python'. "
                "Install with: pip install llama-cpp-python"
            ) from None

        self._llama = Llama(  # type: ignore[assignment]
            model_path=self._model_path,  # type: ignore[arg-type]
            n_ctx=self._context_size,
            n_gpu_layers=self._n_gpu_layers,
            n_threads=self._n_threads,
            verbose=False,
        )
        return self._llama

    # -- LLMProvider interface --------------------------------------------

    def generate_chat(
        self, messages: list[dict[str, str]], **kwargs: Any
    ) -> tuple[str, str]:
        """Generate via Python binding or HTTP server."""
        max_tokens = kwargs.pop("max_tokens", self._max_tokens)

        if self._server_url:
            return self._generate_http(messages, max_tokens, **kwargs)
        return self._generate_binding(messages, max_tokens, **kwargs)

    def count_tokens(self, text: str) -> int:
        """Count tokens via llama.cpp's tokenizer or heuristic fallback."""
        if self._server_url:
            # HTTP mode: heuristic (no local tokenizer available)
            return max(1, len(text) // 4)

        model = self._ensure_model()
        try:
            tokens = model.tokenize(text.encode("utf-8"))
            return len(tokens)
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
        if self._model_path:
            return os.path.basename(self._model_path)
        return f"llamacpp@{self._server_url}"

    # -- private ----------------------------------------------------------

    def _generate_binding(
        self, messages: list[dict[str, str]], max_tokens: int, **kwargs: Any
    ) -> tuple[str, str]:
        """Generate using llama-cpp-python's create_chat_completion."""
        model = self._ensure_model()
        try:
            result = model.create_chat_completion(
                messages=messages,
                max_tokens=max_tokens,
                **kwargs,
            )
            choice = result["choices"][0]
            text = choice["message"]["content"] or ""
            reason = choice.get("finish_reason", "stop")
            if reason == "length":
                pass  # Physical wall
            else:
                reason = "stop"
            return (text, reason)
        except Exception as exc:
            logger.error("llama.cpp binding error: %s", exc)
            return ("", "error")

    def _generate_http(
        self, messages: list[dict[str, str]], max_tokens: int, **kwargs: Any
    ) -> tuple[str, str]:
        """Generate via llama.cpp's OpenAI-compatible HTTP endpoint with retry (§audit H5)."""
        url = f"{self._server_url.rstrip('/')}/v1/chat/completions"  # type: ignore[union-attr]
        payload = json.dumps({
            "messages": messages,
            "max_tokens": max_tokens,
            **kwargs,
        }).encode("utf-8")

        max_retries = 4
        base_delay = 2.0
        last_exc: Exception | None = None

        for attempt in range(max_retries):
            req = urllib.request.Request(
                url,
                data=payload,
                headers={
                    "Content-Type": "application/json",
                    "Connection": "keep-alive",
                },
                method="POST",
            )

            try:
                with urllib.request.urlopen(req, timeout=120) as resp:
                    data = json.loads(resp.read())
                choice = data["choices"][0]
                text = choice["message"]["content"] or ""
                reason = choice.get("finish_reason", "stop")
                if reason != "length":
                    reason = "stop"
                return (text, reason)
            except (urllib.error.URLError, ConnectionError, TimeoutError, OSError) as exc:
                last_exc = exc
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt) + random.uniform(0, 0.5)
                    logger.warning(
                        "llama.cpp HTTP request failed (attempt %d/%d), retrying in %.1fs: %s",
                        attempt + 1, max_retries, delay, exc,
                    )
                    time.sleep(delay)
                    continue
                logger.error("llama.cpp HTTP error after %d retries: %s", max_retries, exc)
                return ("", "error")
            except Exception as exc:
                logger.error("llama.cpp HTTP error (non-retryable): %s", exc)
                return ("", "error")

        logger.error("llama.cpp HTTP failed after %d retries: %s", max_retries, last_exc)
        return ("", "error")

    # ── Tool-mediated dispatch (§20) ──────────────────────────────────

    def supports_tools(self) -> bool:
        """llama.cpp supports OpenAI-compatible tool calling.

        In HTTP-server mode this depends on the server exposing
        ``/v1/chat/completions`` with tool support. In Python-binding mode it
        depends on the underlying ``llama-cpp-python`` version and model.
        CRP advertises support and lets the runtime fail if the model or
        server does not implement it.
        """
        return True

    def generate_chat_with_tools(
        self,
        messages: list[dict[str, object]],
        tools: list[dict[str, object]],
        **kwargs: object,
    ) -> tuple[str, str, list[dict[str, object]] | None, dict[str, object] | None]:
        """Generate with llama.cpp tool/function calling.

        Returns ``(text, finish_reason, tool_calls, raw_assistant_message)``.
        """
        max_tokens = kwargs.pop("max_tokens", self._max_tokens)

        if self._server_url:
            return self._generate_http_with_tools(
                messages, tools, max_tokens, **kwargs
            )
        return self._generate_binding_with_tools(
            messages, tools, max_tokens, **kwargs
        )

    def _generate_binding_with_tools(
        self,
        messages: list[dict[str, object]],
        tools: list[dict[str, object]],
        max_tokens: int,
        **kwargs: object,
    ) -> tuple[str, str, list[dict[str, object]] | None, dict[str, object] | None]:
        """Generate using llama-cpp-python's create_chat_completion with tools."""
        model = self._ensure_model()
        try:
            result = model.create_chat_completion(
                messages=messages,
                tools=tools,
                tool_choice=kwargs.pop("tool_choice", "auto"),
                max_tokens=max_tokens,
                **kwargs,
            )
            return self._parse_tool_response(result)
        except Exception as exc:
            logger.error("llama.cpp binding tool-call error: %s", exc)
            return ("", "error", None, None)

    def _generate_http_with_tools(
        self,
        messages: list[dict[str, object]],
        tools: list[dict[str, object]],
        max_tokens: int,
        **kwargs: object,
    ) -> tuple[str, str, list[dict[str, object]] | None, dict[str, object] | None]:
        """Generate via llama.cpp's OpenAI-compatible HTTP endpoint with tools."""
        url = f"{self._server_url.rstrip('/')}/v1/chat/completions"
        payload = json.dumps({
            "messages": messages,
            "tools": tools,
            "tool_choice": kwargs.pop("tool_choice", "auto"),
            "max_tokens": max_tokens,
            **kwargs,
        }).encode("utf-8")

        max_retries = 4
        base_delay = 2.0
        last_exc: Exception | None = None

        for attempt in range(max_retries):
            req = urllib.request.Request(
                url,
                data=payload,
                headers={
                    "Content-Type": "application/json",
                    "Connection": "keep-alive",
                },
                method="POST",
            )

            try:
                with urllib.request.urlopen(req, timeout=120) as resp:
                    data = json.loads(resp.read())
                return self._parse_tool_response(data)
            except (urllib.error.URLError, ConnectionError, TimeoutError, OSError) as exc:
                last_exc = exc
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt) + random.uniform(0, 0.5)
                    logger.warning(
                        "llama.cpp HTTP tool-call request failed (attempt %d/%d), retrying in %.1fs: %s",
                        attempt + 1, max_retries, delay, exc,
                    )
                    time.sleep(delay)
                    continue
                logger.error("llama.cpp HTTP tool-call error after %d retries: %s", max_retries, exc)
                return ("", "error", None, None)
            except Exception as exc:
                logger.error("llama.cpp HTTP tool-call error (non-retryable): %s", exc)
                return ("", "error", None, None)

        logger.error("llama.cpp HTTP tool-call failed after %d retries: %s", max_retries, last_exc)
        return ("", "error", None, None)

    def _parse_tool_response(
        self,
        data: dict[str, Any],
    ) -> tuple[str, str, list[dict[str, object]] | None, dict[str, object] | None]:
        """Parse an OpenAI-compatible response that may contain tool calls."""
        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {}) or {}
        text = message.get("content", "") or ""
        reason = choice.get("finish_reason", "stop")

        raw_tool_calls = message.get("tool_calls")
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
                "llama.cpp tool calls requested: %d calls [%s]",
                len(tool_calls_out),
                ", ".join(tc["function"]["name"] for tc in tool_calls_out),
            )
            return (text, "tool_calls", tool_calls_out, raw_msg)

        if reason == "length":
            pass
        else:
            reason = "stop"
        return (text, reason, None, None)
