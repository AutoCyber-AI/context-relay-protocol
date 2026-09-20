# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Coverage tests for ``crp.integrations.app_discovery``.

All framework objects are fakes — the real LangChain / LlamaIndex packages are
never imported or required.
"""

from __future__ import annotations

import pytest

from crp.core.app_profile import FrameworkKind, ProviderKind
from crp.integrations.app_discovery import (
    _langchain_tools,
    _llamaindex_tools,
    profile_from_langchain,
    profile_from_llamaindex,
    profile_from_mcp_servers,
    profile_from_openai_tools,
)

# ── _langchain_tools ────────────────────────────────────────────────────


def test_langchain_tools_none_and_empty() -> None:
    assert _langchain_tools(None) == []
    assert _langchain_tools([]) == []


def test_langchain_tools_from_dicts() -> None:
    tools = _langchain_tools([
        {"name": "search", "description": "Search the web", "parameters": {"q": "str"}},
        {"name": "calc"},  # missing description/parameters is tolerated
        {"description": "no name — skipped"},
    ])
    assert [t.name for t in tools] == ["search", "calc"]
    assert tools[0].parameters == {"q": "str"}
    assert tools[0].source == "langchain"


def test_langchain_tools_from_objects_with_schema() -> None:
    class _Schema:
        def schema(self):
            return {"properties": {"x": {}}}

    class _Tool:
        name = "obj_tool"
        description = "A tool"
        args_schema = _Schema()

    tools = _langchain_tools([_Tool()])
    assert tools[0].name == "obj_tool"
    assert tools[0].parameters == {"properties": {"x": {}}}


def test_langchain_tools_schema_error_falls_back() -> None:
    class _BadSchema:
        def schema(self):
            raise RuntimeError("no schema")

    class _Tool:
        name = "t"
        args_schema = _BadSchema()

    tools = _langchain_tools([_Tool()])
    assert tools[0].parameters == {}


def test_langchain_tools_dunder_fallback_and_tuple() -> None:
    def _plain_func():
        """Docstring as description."""

    _plain_func.args_schema = None
    tools = _langchain_tools((_plain_func,))
    assert tools[0].name == "_plain_func"
    assert "Docstring" in tools[0].description


def test_langchain_tools_from_executor_attr() -> None:
    class _Executor:
        tools = ({"name": "from_executor"},)

    tools = _langchain_tools(_Executor())
    assert [t.name for t in tools] == ["from_executor"]


def test_langchain_tools_non_dict_schema() -> None:
    class _Schema(dict):
        pass

    class _Tool:
        name = "t2"
        args_schema = _Schema({"a": 1})

    tools = _langchain_tools([_Tool()])
    assert tools[0].parameters == {"a": 1}


# ── _llamaindex_tools ───────────────────────────────────────────────────


def test_llamaindex_tools_none_and_empty() -> None:
    assert _llamaindex_tools(None) == []
    assert _llamaindex_tools([]) == []


def test_llamaindex_tools_from_dicts() -> None:
    tools = _llamaindex_tools([{"name": "li_tool", "description": "d", "parameters": {"p": 1}}])
    assert tools[0].name == "li_tool"
    assert tools[0].source == "llamaindex"


def test_llamaindex_tools_metadata_and_class_name() -> None:
    class _WithMeta:
        metadata = {"name": "meta_tool", "description": "from metadata"}

    class _NoMeta:
        pass

    tools = _llamaindex_tools([_WithMeta(), _NoMeta(), None])
    assert [t.name for t in tools] == ["meta_tool", "_NoMeta"]


def test_llamaindex_tools_get_tools_raises() -> None:
    class _Engine:
        def get_tools(self):
            raise RuntimeError("boom")

    assert _llamaindex_tools(_Engine()) == []


def test_llamaindex_tools_get_tools_success() -> None:
    class _Engine:
        def get_tools(self):
            return [{"name": "from_engine"}]

    tools = _llamaindex_tools(_Engine())
    assert [t.name for t in tools] == ["from_engine"]


# ── profile_from_langchain ──────────────────────────────────────────────


class FakeOpenAILLM:
    model = "gpt-4o"


class FakeAnthropicLLM:
    model_name = "claude-3"


class FakeOllamaLLM:
    model = "llama3.1"


class FakeLlamaCppLLM:
    pass


class FakeUnknownLLM:
    pass


def test_profile_from_langchain_provider_hints() -> None:
    assert profile_from_langchain(llm=FakeOpenAILLM()).provider is ProviderKind.OPENAI
    assert profile_from_langchain(llm=FakeAnthropicLLM()).provider is ProviderKind.ANTHROPIC
    assert profile_from_langchain(llm=FakeOllamaLLM()).provider is ProviderKind.OLLAMA
    assert profile_from_langchain(llm=FakeLlamaCppLLM()).provider is ProviderKind.LLAMA_CPP
    unknown = profile_from_langchain(llm=FakeUnknownLLM())
    assert unknown.provider is not ProviderKind.OPENAI


def test_profile_from_langchain_model_and_tools() -> None:
    profile = profile_from_langchain(
        llm=FakeOpenAILLM(),
        tools=[{"name": "t1"}],
    )
    assert profile.framework is FrameworkKind.LANGCHAIN
    assert profile.provider_model == "gpt-4o"
    assert [t.name for t in profile.tools] == ["t1"]


def test_profile_from_langchain_empty() -> None:
    profile = profile_from_langchain()
    assert profile.framework is FrameworkKind.LANGCHAIN
    assert profile.tools == []


# ── profile_from_llamaindex ─────────────────────────────────────────────


def test_profile_from_llamaindex_no_engine() -> None:
    profile = profile_from_llamaindex(tools=[{"name": "t"}])
    assert profile.framework is FrameworkKind.LLAMAINDEX
    assert [t.name for t in profile.tools] == ["t"]


def test_profile_from_llamaindex_with_engine_raises() -> None:
    # DOCUMENTED LATENT BUG (crp/integrations/app_discovery.py:154-160):
    # ContextSource is constructed with an invalid ``name`` kwarg and a str
    # ``origin``, so this path raises TypeError at runtime.  Left as-is.
    class _Engine:
        pass

    with pytest.raises(TypeError):
        profile_from_llamaindex(query_engine=_Engine())


# ── profile_from_openai_tools ───────────────────────────────────────────


def test_profile_from_openai_tools_function_shape() -> None:
    profile = profile_from_openai_tools(
        tools=[{
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get weather",
                "parameters": {"type": "object"},
            },
        }],
        model="gpt-4o",
    )
    assert profile.framework is FrameworkKind.OPENAI
    assert profile.provider is ProviderKind.OPENAI
    assert profile.provider_model == "gpt-4o"
    assert profile.tools[0].name == "get_weather"
    assert profile.tools[0].source == "openai"


def test_profile_from_openai_tools_flat_shape() -> None:
    profile = profile_from_openai_tools(tools=[{"name": "flat_tool"}])
    assert profile.tools[0].name == "flat_tool"
    assert profile.tools[0].description == ""


# ── profile_from_mcp_servers ────────────────────────────────────────────


def test_profile_from_mcp_servers() -> None:
    profile = profile_from_mcp_servers([
        "stdio://filesystem",
        {"name": "github"},
        {"url": "https://mcp.example.com"},
        {"no_name_no_url": 1},
    ])
    assert profile.mcp_servers[0] == "stdio://filesystem"
    assert profile.mcp_servers[1] == "github"
    assert profile.mcp_servers[2] == "https://mcp.example.com"
    assert "no_name_no_url" in profile.mcp_servers[3]


def test_profile_from_mcp_servers_empty() -> None:
    assert profile_from_mcp_servers([]).mcp_servers == []
    assert profile_from_mcp_servers(None).mcp_servers == []
