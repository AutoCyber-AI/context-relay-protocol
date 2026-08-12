"""Integration tests for ApplicationProfile wiring into orchestrator and SDK."""

from __future__ import annotations

import pytest

from crp.core.app_profile import (
    ApplicationProfile,
    ContextStrategy,
    FrameworkKind,
    ProviderKind,
    ToolInfo,
    build_profile_from_messages,
)
from crp.core.orchestrator import CRPOrchestrator
from crp.providers.base import LLMProvider
from crp.providers.openai import OpenAIAdapter
from crp.sdk.client import CRPClient


class _ToolableProvider(LLMProvider):
    """Mock provider that advertises tool support."""

    def __init__(self) -> None:
        self._name = "mock-toolable"

    def generate_chat(
        self, messages: list[dict[str, str]], **kwargs: object
    ) -> tuple[str, str]:
        return ("push answer", "stop")

    def count_tokens(self, text: str) -> int:
        return len(text.split())

    def context_window_size(self) -> int:
        return 4096

    def supports_tools(self) -> bool:
        return True

    def generate_chat_with_tools(
        self,
        messages: list[dict[str, object]],
        tools: list[dict[str, object]],
        **kwargs: object,
    ) -> tuple[str, str, list[dict[str, object]] | None, dict[str, object] | None]:
        return (
            "tool-mediated answer",
            "stop",
            None,
            {"role": "assistant", "content": "tool-mediated answer"},
        )


class _PlainProvider(LLMProvider):
    """Mock provider without tool support."""

    def generate_chat(
        self, messages: list[dict[str, str]], **kwargs: object
    ) -> tuple[str, str]:
        return ("plain answer", "stop")

    def count_tokens(self, text: str) -> int:
        return len(text.split())

    def context_window_size(self) -> int:
        return 4096


class TestOrchestratorProfileWiring:
    def test_orchestrator_stores_profile(self):
        profile = ApplicationProfile(
            framework=FrameworkKind.LANGCHAIN,
            provider=ProviderKind.OPENAI,
        )
        orch = CRPOrchestrator(provider=_ToolableProvider(), app_profile=profile)
        assert orch._app_profile.framework is FrameworkKind.LANGCHAIN
        assert orch._app_profile.provider is ProviderKind.OPENAI

    def test_select_tools_strategy_when_profile_has_tools(self):
        orch = CRPOrchestrator(
            provider=_ToolableProvider(),
            app_profile=ApplicationProfile(tools=[ToolInfo(name="search")]),
        )
        assert orch._select_relay_strategy() == "tools"

    def test_select_reflexive_for_summarization(self):
        orch = CRPOrchestrator(
            provider=_ToolableProvider(),
            app_profile=ApplicationProfile(
                context_strategy=ContextStrategy.SUMMARIZATION
            ),
        )
        assert orch._select_relay_strategy() == "reflexive"

    def test_select_progressive_for_sliding_window(self):
        orch = CRPOrchestrator(
            provider=_ToolableProvider(),
            app_profile=ApplicationProfile(
                context_strategy=ContextStrategy.SLIDING_WINDOW
            ),
        )
        assert orch._select_relay_strategy() == "progressive"

    def test_select_stream_augmented_for_long_context(self):
        orch = CRPOrchestrator(
            provider=_ToolableProvider(),
            app_profile=ApplicationProfile(
                context_strategy=ContextStrategy.LONG_CONTEXT
            ),
        )
        assert orch._select_relay_strategy() == "stream_augmented"

    def test_select_agentic_for_hybrid(self):
        orch = CRPOrchestrator(
            provider=_ToolableProvider(),
            app_profile=ApplicationProfile(context_strategy=ContextStrategy.HYBRID),
        )
        assert orch._select_relay_strategy() == "agentic"

    def test_select_push_default(self):
        orch = CRPOrchestrator(provider=_ToolableProvider())
        assert orch._select_relay_strategy() == "push"

    def test_select_tools_for_registered_sdk_tools(self):
        orch = CRPOrchestrator(provider=_ToolableProvider())
        assert orch._select_relay_strategy(has_registered_tools=True) == "tools"

    def test_dispatch_with_strategy_routes_to_tools(self):
        orch = CRPOrchestrator(
            provider=_ToolableProvider(),
            app_profile=ApplicationProfile(tools=[ToolInfo(name="search")]),
        )
        output, report = orch.dispatch_with_strategy(
            "tools", "system", "hello"
        )
        assert output == "tool-mediated answer"
        assert report is not None

    def test_dispatch_with_unknown_strategy_falls_back(self):
        orch = CRPOrchestrator(provider=_PlainProvider())
        output, report = orch.dispatch_with_strategy(
            "not-a-strategy", "system", "hello"
        )
        assert output == "plain answer"
        assert report is not None


class TestSdkProfileWiring:
    def test_client_accepts_app_profile(self):
        profile = ApplicationProfile(
            provider=ProviderKind.OPENAI,
            provider_model="gpt-4o",
        )
        client = CRPClient(app_profile=profile)
        assert client.app_profile is profile
        orch = client._ensure_orchestrator()
        assert orch._app_profile is profile

    def test_client_resolves_provider_from_profile(self):
        profile = ApplicationProfile(
            provider=ProviderKind.OPENAI,
            provider_model="gpt-4o",
        )
        client = CRPClient(app_profile=profile)
        orch = client._ensure_orchestrator()
        assert isinstance(orch._provider, OpenAIAdapter)
        assert orch._provider.model_name == "gpt-4o"

    def test_client_routes_to_dispatch_with_tools_from_profile(self):
        profile = ApplicationProfile(tools=[ToolInfo(name="search")])
        client = CRPClient(provider=_ToolableProvider(), app_profile=profile)
        response = client.complete("hello")
        assert response.text == "tool-mediated answer"

    def test_client_derive_profile_from_messages(self):
        client = CRPClient(provider=_PlainProvider())
        messages = [
            {"role": "system", "content": "Keep only the last 10 messages."},
        ]
        profile = client.derive_profile(messages)
        assert profile.context_strategy is ContextStrategy.SLIDING_WINDOW

    def test_client_derive_profile_from_tools(self):
        client = CRPClient(provider=_PlainProvider())
        tools = [{"type": "function", "function": {"name": "get_weather"}}]
        profile = client.derive_profile([], tools=tools)
        assert profile.tools[0].name == "get_weather"


class TestProfileProviderResolution:
    def test_profile_lm_studio_provider(self):
        from crp.sdk.client import _provider_from_profile

        profile = ApplicationProfile(
            provider=ProviderKind.LM_STUDIO,
            provider_model="llama-3.1-8b",
        )
        provider = _provider_from_profile(profile)
        assert isinstance(provider, OpenAIAdapter)
        assert provider.model_name == "llama-3.1-8b"

    def test_profile_llama_cpp_provider(self):
        from crp.sdk.client import _provider_from_profile

        profile = ApplicationProfile(provider=ProviderKind.LLAMA_CPP)
        provider = _provider_from_profile(profile)
        from crp.providers.llamacpp import LlamaCppAdapter

        assert isinstance(provider, LlamaCppAdapter)
