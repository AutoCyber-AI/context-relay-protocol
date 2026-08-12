# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""LLMProviderManager — multi-provider routing with fallback chain (§5; CRP-SPEC-008).

Supports:
  - Primary provider selection
  - Fallback chain: if primary fails, try registered providers in order
  - Provider registration and retrieval by name

Relevant specifications:
  - CRP specification §5: Provider routing
  - CRP-SPEC-008: Dispatch & Provider Adaptation
"""

from __future__ import annotations

import logging

from crp.core.errors import ProviderError
from crp.providers.base import LLMProvider

logger = logging.getLogger("crp.providers.manager")


class LLMProviderManager:
    """Routes requests to one or more LLM providers with fallback.

    Usage::

        mgr = LLMProviderManager(primary_provider)
        mgr.register(fallback_provider)

        # Generate with automatic fallback
        output, reason = mgr.generate_with_fallback(messages)

    Args:
        provider: Primary LLM provider.  It is also registered under its
            ``model_name`` for internal lookup.
    """

    def __init__(self, provider: LLMProvider) -> None:
        self._primary = provider
        self._providers: dict[str, LLMProvider] = {provider.model_name: provider}
        self._fallback_order: list[str] = []  # model names in fallback priority

    @property
    def primary(self) -> LLMProvider:
        """Return the primary provider."""
        return self._primary

    @property
    def provider_count(self) -> int:
        """Return the number of registered providers."""
        return len(self._providers)

    @property
    def provider_names(self) -> list[str]:
        """Return the names of all registered providers."""
        return list(self._providers.keys())

    def register(self, provider: LLMProvider) -> None:
        """Register an additional provider for fallback routing.

        Args:
            provider: Provider to add to the routing table.
        """
        self._providers[provider.model_name] = provider
        if provider.model_name != self._primary.model_name:
            self._fallback_order.append(provider.model_name)
        logger.info("Provider registered: %s (total: %d)", provider.model_name, len(self._providers))

    def get(self, name: str | None = None) -> LLMProvider:
        """Get a provider by name, or the primary if *name* is None.

        Args:
            name: Provider name, or None to retrieve the primary provider.

        Returns:
            The requested ``LLMProvider``.

        Raises:
            ProviderError: If ``name`` is supplied but no matching provider is
                registered.
        """
        if name is None:
            return self._primary
        provider = self._providers.get(name)
        if provider is None:
            raise ProviderError(
                f"Provider '{name}' not registered",
                available=list(self._providers.keys()),
            )
        return provider

    def generate_with_fallback(
        self,
        messages: list[dict[str, str]],
        **kwargs: object,
    ) -> tuple[str, str, str]:
        """Generate using primary, fall back to registered providers on failure.

        Args:
            messages: Chat messages to send.
            **kwargs: Provider-specific overrides passed to ``generate_chat``.

        Returns:
            ``(output_text, finish_reason, provider_name)`` — the provider that
            successfully generated is identified in ``provider_name``.

        Raises:
            ProviderError: If ALL providers fail.
        """
        providers_to_try = [self._primary.model_name] + self._fallback_order
        last_error: Exception | None = None

        for name in providers_to_try:
            provider = self._providers.get(name)
            if provider is None:
                continue
            try:
                output, finish_reason = provider.generate_chat(messages, **kwargs)
                if name != self._primary.model_name:
                    logger.warning(
                        "Primary provider failed, fell back to '%s'", name,
                    )
                return output, finish_reason, name
            except Exception as exc:
                logger.warning("Provider '%s' failed: %s", name, exc)
                last_error = exc
                continue

        raise ProviderError(
            f"All {len(providers_to_try)} providers failed",
            available=list(self._providers.keys()),
        ) from last_error

    def generate_with_tools_fallback(
        self,
        messages: list[dict[str, object]],
        tools: list[dict[str, object]],
        **kwargs: object,
    ) -> tuple[str, str, list[dict[str, object]] | None, dict[str, object] | None, str]:
        """Generate with tools using primary, fall back on failure.

        Only providers that report ``supports_tools() == True`` are considered.

        Args:
            messages: Chat messages (may include tool messages).
            tools: OpenAI-compatible tool definitions.
            **kwargs: Provider-specific overrides passed to
                ``generate_chat_with_tools``.

        Returns:
            ``(output_text, finish_reason, tool_calls, raw_message, provider_name)``.

        Raises:
            ProviderError: If no tool-capable provider succeeds.
        """
        providers_to_try = [self._primary.model_name] + self._fallback_order
        last_error: Exception | None = None

        for name in providers_to_try:
            provider = self._providers.get(name)
            if provider is None or not provider.supports_tools():
                continue
            try:
                result = provider.generate_chat_with_tools(messages, tools, **kwargs)
                if name != self._primary.model_name:
                    logger.warning("Tools fallback to '%s'", name)
                return (*result, name)
            except Exception as exc:
                logger.warning("Provider '%s' tools failed: %s", name, exc)
                last_error = exc
                continue

        raise ProviderError(
            "All providers failed for tool-mediated dispatch",
            available=list(self._providers.keys()),
        ) from last_error
