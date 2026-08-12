"""Tests for ApplicationProfile / application capability contract."""

from __future__ import annotations

import pytest

from crp.core.app_profile import (
    ApplicationProfile,
    ContextStrategy,
    FrameworkKind,
    ProviderKind,
    ToolInfo,
    build_profile_from_messages,
    detect_context_strategy,
    detect_framework,
)
from crp.core.context_source import ContextSource, SourceKind


class TestApplicationProfile:
    def test_default_profile_is_unknown(self):
        profile = ApplicationProfile()
        assert profile.framework is FrameworkKind.UNKNOWN
        assert profile.provider is ProviderKind.UNKNOWN
        assert profile.supports_tools() is False

    def test_supports_tools_with_tools(self):
        profile = ApplicationProfile(tools=[ToolInfo(name="search")])
        assert profile.supports_tools() is True

    def test_supports_tools_with_mcp_servers(self):
        profile = ApplicationProfile(mcp_servers=["memory"])
        assert profile.supports_tools() is True

    def test_to_dict_round_trip(self):
        profile = ApplicationProfile(
            framework=FrameworkKind.LANGCHAIN,
            provider=ProviderKind.OPENAI,
            provider_model="gpt-4o",
            context_window=128_000,
            context_strategy=ContextStrategy.RAG,
            tools=[ToolInfo(name="search", description="Search docs")],
            rag_sources=[ContextSource(kind=SourceKind.VECTOR_DB, source_id="kb")],
        )
        restored = ApplicationProfile.from_dict(profile.to_dict())
        assert restored.framework is FrameworkKind.LANGCHAIN
        assert restored.provider_model == "gpt-4o"
        assert restored.tools[0].name == "search"
        assert restored.rag_sources[0].source_id == "kb"


class TestFrameworkDetection:
    def test_empty_messages(self):
        assert detect_framework([]) is FrameworkKind.UNKNOWN

    def test_openai_tool_messages(self):
        messages = [
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "", "tool_calls": [{"id": "c1"}]},
            {"role": "tool", "content": "result", "tool_call_id": "c1"},
        ]
        assert detect_framework(messages) is FrameworkKind.OPENAI

    def test_langchain_metadata(self):
        messages = [
            {"role": "user", "content": "Hi", "metadata": {"langchain": True}},
        ]
        assert detect_framework(messages) is FrameworkKind.LANGCHAIN


class TestContextStrategyDetection:
    def test_summarization_prompt(self):
        messages = [
            {"role": "system", "content": "Summarize the conversation so far."},
        ]
        assert detect_context_strategy(messages) is ContextStrategy.SUMMARIZATION

    def test_sliding_window_prompt(self):
        messages = [
            {"role": "system", "content": "Keep only the last 10 messages."},
        ]
        assert detect_context_strategy(messages) is ContextStrategy.SLIDING_WINDOW


class TestBuildProfileFromMessages:
    def test_tools_derived(self):
        tools = [{"type": "function", "function": {"name": "get_weather", "description": "weather"}}]
        profile = build_profile_from_messages([], tools=tools)
        assert profile.tools[0].name == "get_weather"

    def test_rag_detected_from_metadata(self):
        messages = [{
            "role": "assistant",
            "content": "Here is the answer.",
            "metadata": {"sources": [{"name": "doc1", "content": "fact"}]},
        }]
        profile = build_profile_from_messages(messages)
        assert profile.context_strategy is ContextStrategy.RAG
        assert profile.rag_sources[0].source_id == "doc1"
        assert "fact" in profile.rag_sources[0].metadata.get("snippet", "")
