# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""CRP Gateway — Provider Router.

Routes outbound LLM requests to the correct provider based on the model name
and tenant configuration.  Implements failover between providers.

Supported providers: openai, anthropic, local (LM Studio / Ollama)
Future: gemini, bedrock (SPEC-016 §10).

SPEC-016 §8.
"""

from __future__ import annotations

import dataclasses
import json
import logging
import os
import time
import urllib.error
import urllib.request
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from crp.gateway.key_vault import KeyVault

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Provider model-name routing map
# ---------------------------------------------------------------------------

#: Model-name prefixes to provider slug mapping.
_MODEL_PREFIX_TO_PROVIDER: dict[str, str] = {
    "gpt-": "openai",
    "o1": "openai",
    "o3": "openai",
    "o4": "openai",
    "claude-": "anthropic",
    "gemini-": "gemini",
    "mistral": "local",
    "llama": "local",
    "qwen": "local",
    "phi": "local",
    "deepseek": "local",
}

#: Default local LM Studio / Ollama base URL.
_DEFAULT_LOCAL_URL = os.environ.get("CRP_LOCAL_LLM_URL", "http://127.0.0.1:1234")

#: Default Anthropic API version header.
_ANTHROPIC_VERSION = "2023-06-01"


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class ProviderConfig:
    """Resolved configuration for a single provider call."""

    provider_slug: str
    base_url: str
    api_key: str
    model: str
    extra_headers: dict[str, str] = dataclasses.field(default_factory=dict)
    # Constrained-decoding capability: "json_schema" (OpenAI strict),
    # "gbnf" (llama.cpp grammar), or None (validate+repair only).
    constrained_decoding: str | None = None


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------


class ProviderRouter:
    """Route an outbound request to the correct LLM provider.

    The router is stateless per-request.  It resolves the provider from the
    model name, fetches the API key from the KeyVault, applies failover on
    transient errors, and returns a normalised ProviderResponse.

    Args:
        key_vault: KeyVault instance.  If None, a new ephemeral vault is
            created (useful for local development where keys come from env vars).
        local_url: Override for the local LM Studio / Ollama base URL.
    """

    def __init__(
        self,
        key_vault: KeyVault | None = None,
        local_url: str | None = None,
        ckf: Any | None = None,
        local_constrained: str | None = None,
    ) -> None:
        from crp.gateway.key_vault import KeyVault  # local import to avoid circular

        self._vault: KeyVault = key_vault or KeyVault()
        self._local_url = local_url or _DEFAULT_LOCAL_URL
        self.ckf = ckf
        # Set to "gbnf" when local_url points at a llama.cpp server.
        self._local_constrained = local_constrained

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def resolve_provider(self, model: str, tenant_id: str) -> ProviderConfig:
        """Resolve which provider handles *model* for *tenant_id*.

        Provider selection priority:
          1. Explicit tenant override (future: from tenant config store).
          2. Model-name prefix table.
          3. Default: local.

        Returns a ProviderConfig with the resolved base URL, API key,
        and any provider-specific extra headers.
        """
        slug = self._model_to_slug(model)
        api_key = self._vault.get_provider_key(tenant_id, slug)

        if slug == "openai":
            return ProviderConfig(
                provider_slug="openai",
                base_url="https://api.openai.com",
                api_key=api_key,
                model=model,
                constrained_decoding="json_schema",
            )
        if slug == "anthropic":
            return ProviderConfig(
                provider_slug="anthropic",
                base_url="https://api.anthropic.com",
                api_key=api_key,
                model=model,
                extra_headers={"anthropic-version": _ANTHROPIC_VERSION},
            )
        if slug == "gemini":
            return ProviderConfig(
                provider_slug="gemini",
                base_url="https://generativelanguage.googleapis.com",
                api_key=api_key,
                model=model,
            )
        # Default → local (LM Studio / Ollama, OpenAI-compatible)
        return ProviderConfig(
            provider_slug="local",
            base_url=self._local_url,
            api_key=api_key or "local",
            model=model,
            constrained_decoding=self._local_constrained,
        )

    def dispatch(
        self,
        request: Any,
        messages: list[Any],
        session: Any,
    ) -> Any:
        """Dispatch a chat completion request to the resolved provider.

        Attempts the primary provider.  On transient error (5xx, timeout)
        tries once more with the same config (cold retry).  Hard errors
        (auth failure, quota) propagate immediately.

        Args:
            request: ChatRequest from api.py.
            messages: Augmented message list (post-CDR envelope).
            session: GatewaySession (used for tenant_id, logging).

        Returns:
            ProviderResponse populated with content + token counts.
        """
        from crp.gateway.api import ProviderResponse  # avoid circular at module level

        config = self.resolve_provider(request.model, session.tenant_id)
        body = self._build_request_body(request, messages, config)
        headers = self._build_request_headers(config)

        # Primary attempt
        try:
            return self._call_provider(config, body, headers)
        except _TransientError as exc:
            logger.warning("Provider transient error, retrying once: %s", exc)

        # One cold retry (SPEC-016 §10)
        try:
            return self._call_provider(config, body, headers)
        except _TransientError as exc:
            logger.error("Provider retry also failed: %s", exc)
            # Return empty response rather than crashing the lifecycle
            return ProviderResponse(
                content="[CRP Gateway: provider unavailable]",
                model=config.model,
                finish_reason="error",
            )

    def failover(self, primary_slug: str) -> str:
        """Return the failover provider slug for *primary_slug* (SPEC-016 §10)."""
        fallbacks: dict[str, str] = {
            "openai": "anthropic",
            "anthropic": "openai",
            "gemini": "openai",
            "local": "local",
        }
        return fallbacks.get(primary_slug, "local")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _model_to_slug(self, model: str) -> str:
        lower = model.lower()
        for prefix, slug in _MODEL_PREFIX_TO_PROVIDER.items():
            if lower.startswith(prefix):
                return slug
        return "local"

    def _build_request_body(
        self,
        request: Any,
        messages: list[Any],
        config: ProviderConfig,
    ) -> dict[str, Any]:
        """Build the provider-specific request body."""
        msg_dicts = [m.to_dict() if hasattr(m, "to_dict") else m for m in messages]
        body: dict[str, Any] = {
            "model": config.model,
            "messages": msg_dicts,
        }
        if request.temperature is not None:
            body["temperature"] = request.temperature
        if request.max_tokens is not None:
            body["max_tokens"] = request.max_tokens
        if getattr(request, "tools", None):
            body["tools"] = request.tools
        if getattr(request, "tool_choice", None) is not None:
            body["tool_choice"] = request.tool_choice
        if getattr(request, "response_format", None) is not None:
            body["response_format"] = request.response_format
        if getattr(request, "grammar", None):
            # llama.cpp GBNF grammar field (SPEC-054 constrained decoding)
            body["grammar"] = request.grammar
        # Anthropic uses a different key
        if config.provider_slug == "anthropic":
            body["max_tokens"] = request.max_tokens or 4096
        return body

    def _build_request_headers(self, config: ProviderConfig) -> dict[str, str]:
        """Build stripped, provider-safe request headers."""
        headers: dict[str, str] = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {config.api_key}",
        }
        if config.provider_slug == "anthropic":
            # Anthropic uses x-api-key instead of Bearer
            headers.pop("Authorization", None)
            headers["x-api-key"] = config.api_key
        headers.update(config.extra_headers)
        return headers

    def _call_provider(
        self,
        config: ProviderConfig,
        body: dict[str, Any],
        headers: dict[str, str],
    ) -> Any:
        """Execute a single HTTP call to the provider (stdlib urllib, no deps)."""

        if config.provider_slug == "anthropic":
            endpoint = f"{config.base_url}/v1/messages"
        elif config.provider_slug == "gemini":
            endpoint = (
                f"{config.base_url}/v1beta/models/{config.model}"
                f":generateContent?key={config.api_key}"
            )
        else:
            endpoint = f"{config.base_url}/v1/chat/completions"

        payload = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            endpoint,
            data=payload,
            headers=headers,
            method="POST",
        )

        t0 = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                raw_body = json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            if exc.code and exc.code >= 500:
                raise _TransientError(f"HTTP {exc.code} from {config.provider_slug}") from exc
            # 4xx = hard error (auth, quota, bad request) — propagate
            error_body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"Provider {config.provider_slug} returned HTTP {exc.code}: {error_body[:200]}"
            ) from exc
        except (urllib.error.URLError, OSError) as exc:
            raise _TransientError(f"Network error calling {config.provider_slug}: {exc}") from exc

        elapsed = (time.perf_counter() - t0) * 1000
        logger.debug("Provider=%s elapsed=%.0fms", config.provider_slug, elapsed)

        return _parse_provider_response(raw_body, config)


def _parse_provider_response(raw: dict[str, Any], config: ProviderConfig) -> Any:
    """Parse a provider-specific JSON response to a normalised ProviderResponse."""
    from crp.gateway.api import ProviderResponse

    if config.provider_slug == "anthropic":
        # Anthropic Messages API response format
        content = ""
        for block in raw.get("content", []):
            if isinstance(block, dict) and block.get("type") == "text":
                content += block.get("text", "")
        usage = raw.get("usage", {})
        return ProviderResponse(
            content=content,
            model=raw.get("model", config.model),
            finish_reason=raw.get("stop_reason", "end_turn"),
            prompt_tokens=usage.get("input_tokens", 0),
            completion_tokens=usage.get("output_tokens", 0),
            raw=raw,
        )

    # OpenAI-compatible (also LM Studio / Ollama)
    choices = raw.get("choices", [{}])
    first = choices[0] if choices else {}
    message = first.get("message", {})
    usage = raw.get("usage", {})
    return ProviderResponse(
        content=message.get("content", ""),
        model=raw.get("model", config.model),
        finish_reason=first.get("finish_reason", "stop"),
        prompt_tokens=usage.get("prompt_tokens", 0),
        completion_tokens=usage.get("completion_tokens", 0),
        raw=raw,
    )


class _TransientError(Exception):
    """Provider transient error that may be retried."""
