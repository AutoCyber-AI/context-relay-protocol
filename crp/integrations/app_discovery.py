# Copyright © 2025-2026 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Discover an existing application's tools and context strategy.

This module introspects common LLM frameworks *without* hard-depending on them.
Every import of an external package is guarded so CRP still works when the
framework is not installed.
"""

from __future__ import annotations

from typing import Any

from crp.core.app_profile import (
    ApplicationProfile,
    ContextStrategy,
    FrameworkKind,
    ProviderKind,
    ToolInfo,
)
from crp.core.context_source import ContextSource, SourceKind


def _langchain_tools(obj: Any) -> list[ToolInfo]:
    """Extract ToolInfo objects from a LangChain tool list or agent executor."""
    tools: list[ToolInfo] = []
    if obj is None:
        return tools

    items: list[Any] = []
    if isinstance(obj, (list, tuple)):
        items = list(obj)
    elif hasattr(obj, "tools") and isinstance(getattr(obj, "tools"), (list, tuple)):
        items = list(getattr(obj, "tools"))

    for item in items:
        if item is None:
            continue
        name = ""
        description = ""
        params: dict[str, Any] = {}

        if isinstance(item, dict):
            name = item.get("name", "")
            description = item.get("description", "")
            params = item.get("parameters", item.get("args_schema", {}))
        else:
            name = getattr(item, "name", "") or getattr(item, "__name__", "")
            description = getattr(item, "description", "") or getattr(item, "__doc__", "")
            schema = getattr(item, "args_schema", None)
            if schema is not None:
                try:
                    params = schema.schema() if hasattr(schema, "schema") else dict(schema)
                except Exception:
                    params = {}

        if name:
            tools.append(ToolInfo(
                name=name,
                description=str(description)[:500],
                parameters=params if isinstance(params, dict) else {},
                source="langchain",
            ))
    return tools


def _llamaindex_tools(obj: Any) -> list[ToolInfo]:
    """Extract ToolInfo objects from a LlamaIndex QueryEngine or tool list."""
    tools: list[ToolInfo] = []
    if obj is None:
        return tools

    items: list[Any] = []
    if isinstance(obj, (list, tuple)):
        items = list(obj)
    elif hasattr(obj, "get_tools"):
        try:
            items = list(obj.get_tools())
        except Exception:
            pass

    for item in items:
        if item is None:
            continue
        name = ""
        description = ""
        params: dict[str, Any] = {}

        if isinstance(item, dict):
            name = item.get("name", "")
            description = item.get("description", "")
            params = item.get("parameters", {})
        else:
            name = getattr(item, "metadata", {}).get("name", "") if hasattr(item, "metadata") else ""
            if not name:
                name = getattr(item, "__class__", type(item)).__name__
            description = getattr(item, "metadata", {}).get("description", "")

        if name:
            tools.append(ToolInfo(
                name=name,
                description=str(description)[:500],
                parameters=params,
                source="llamaindex",
            ))
    return tools


def profile_from_langchain(
    llm: Any | None = None,
    tools: Any | None = None,
    chain: Any | None = None,
) -> ApplicationProfile:
    """Build an :class:`ApplicationProfile` from a LangChain setup.

    Args:
        llm: A LangChain LLM/chat-model instance (used for provider hints).
        tools: A list of LangChain tools or an agent/executor with ``.tools``.
        chain: A LangChain chain (used for framework detection).
    """
    profile = ApplicationProfile(framework=FrameworkKind.LANGCHAIN)

    # Provider hint from LLM class name / model kwargs
    if llm is not None:
        cls_name = getattr(llm, "__class__", type(llm)).__name__.lower()
        if "openai" in cls_name:
            profile.provider = ProviderKind.OPENAI
        elif "anthropic" in cls_name:
            profile.provider = ProviderKind.ANTHROPIC
        elif "ollama" in cls_name:
            profile.provider = ProviderKind.OLLAMA
        elif "llama" in cls_name:
            profile.provider = ProviderKind.LLAMA_CPP

        model = getattr(llm, "model", "") or getattr(llm, "model_name", "")
        if isinstance(model, str):
            profile.provider_model = model

    profile.tools = _langchain_tools(tools)
    return profile


def profile_from_llamaindex(
    query_engine: Any | None = None,
    tools: Any | None = None,
) -> ApplicationProfile:
    """Build an :class:`ApplicationProfile` from a LlamaIndex setup."""
    profile = ApplicationProfile(framework=FrameworkKind.LLAMAINDEX)
    profile.tools = _llamaindex_tools(tools)

    if query_engine is not None:
        # Best-effort: mark RAG if a query engine is present.
        profile.context_strategy = ContextStrategy.RAG
        profile.rag_sources.append(ContextSource(
            kind=SourceKind.RAG_RETRIEVAL,
            name=getattr(query_engine, "__class__", type(query_engine)).__name__,
            origin="DECLARED",
        ))

    return profile


def profile_from_openai_tools(
    tools: list[dict[str, Any]],
    model: str = "",
) -> ApplicationProfile:
    """Build an :class:`ApplicationProfile` from an OpenAI-style tool list."""
    profile = ApplicationProfile(
        framework=FrameworkKind.OPENAI,
        provider=ProviderKind.OPENAI,
        provider_model=model,
    )
    for tool in tools:
        func = tool.get("function", {}) or tool
        profile.tools.append(ToolInfo(
            name=func.get("name", tool.get("name", "unknown")),
            description=func.get("description", ""),
            parameters=func.get("parameters", {}),
            source="openai",
        ))
    return profile


def profile_from_mcp_servers(
    servers: list[str] | list[dict[str, Any]],
) -> ApplicationProfile:
    """Build an :class:`ApplicationProfile` from a list of MCP server refs."""
    profile = ApplicationProfile()
    for srv in servers or []:
        if isinstance(srv, str):
            profile.mcp_servers.append(srv)
        elif isinstance(srv, dict):
            profile.mcp_servers.append(srv.get("name", srv.get("url", str(srv))))
    return profile
