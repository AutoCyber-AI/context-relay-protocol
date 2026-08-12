# Copyright © 2025-2026 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Application capability contract and strategy discovery (CRP-SPEC-008 extension).

Most applications already have their own context-management and tool-calling
strategy before CRP is introduced: a LangChain chain with a set of tools, a
LlamaIndex RAG pipeline, a custom sliding-window summariser, etc.  Rather than
forcing the integrator to throw that away, :class:`ApplicationProfile` lets CRP
*discover* or be *told* what the application already does, so CRP can:

1. Avoid duplicating existing retrieval (don't build a second vector index if
   the app already has one).
2. Delegate tool execution to the application's own tool registry when possible.
3. Choose a compatible relay strategy (push vs pull vs reflexive) based on the
   app's actual provider and context budget.
4. Record provenance accurately for audit (this fact came from the app's
   existing RAG, not from CRP's warm store).

The profile is intentionally a *contract*, not a config file.  It can be:

* **Declared** by the integrator (authoritative).
* **Derived** from a message list and an optional tool list (heuristic).
* **Detected** from a framework object such as a LangChain ``BaseCallbackHandler``
  or LlamaIndex ``QueryEngine`` (best-effort).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from crp.core.context_source import ContextManifest, ContextSource, SourceKind, SourceOrigin


class FrameworkKind(str, Enum):
    """Known application/framework integrations."""

    UNKNOWN = "unknown"
    LANGCHAIN = "langchain"
    LLAMAINDEX = "llamaindex"
    HAYSTACK = "haystack"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    CUSTOM = "custom"


class ContextStrategy(str, Enum):
    """How the application manages long conversation context."""

    UNKNOWN = "unknown"
    FULL_HISTORY = "full_history"          # Replays every turn verbatim
    SLIDING_WINDOW = "sliding_window"      # Keeps last N turns
    SUMMARIZATION = "summarization"        # Condenses old turns
    RAG = "rag"                            # Retrieves relevant chunks
    LONG_CONTEXT = "long_context"          # Relies on huge native context
    HYBRID = "hybrid"                      # Mix of the above


class ProviderKind(str, Enum):
    """Broad provider families CRP knows how to govern."""

    UNKNOWN = "unknown"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    OLLAMA = "ollama"
    LLAMA_CPP = "llama_cpp"
    LM_STUDIO = "lm_studio"
    CUSTOM = "custom"


@dataclass
class ToolInfo:
    """A tool the application already exposes."""

    name: str
    description: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)
    source: str = "declared"   # "declared" | "derived" | "mcp" | "langchain" | ...


@dataclass
class ApplicationProfile:
    """Capability contract for an existing application.

    Fields are optional; missing fields mean "unknown / not provided" and CRP
    falls back to its own defaults.
    """

    framework: FrameworkKind = FrameworkKind.UNKNOWN
    provider: ProviderKind = ProviderKind.UNKNOWN
    provider_model: str = ""
    context_window: int | None = None
    max_output_tokens: int | None = None
    context_strategy: ContextStrategy = ContextStrategy.UNKNOWN
    tools: list[ToolInfo] = field(default_factory=list)
    mcp_servers: list[str] = field(default_factory=list)
    rag_sources: list[ContextSource] = field(default_factory=list)
    long_context_caching: bool = False
    sliding_window_size: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def supports_tools(self) -> bool:
        """Return True if the profile indicates tool-calling is available."""
        return len(self.tools) > 0 or len(self.mcp_servers) > 0

    def to_manifest(self) -> ContextManifest:
        """Convert the profile's RAG/sources into a :class:`ContextManifest`."""
        manifest = ContextManifest()
        for src in self.rag_sources:
            manifest.add(src)
        if self.context_strategy in {ContextStrategy.RAG, ContextStrategy.HYBRID}:
            # Add a generic RAG placeholder if no explicit sources were given.
            if not self.rag_sources:
                manifest.add(ContextSource(
                    kind=SourceKind.RAG_RETRIEVAL,
                    source_id="application_rag",
                    origin=SourceOrigin.DECLARED,
                ))
        for tool in self.tools:
            manifest.add(ContextSource(
                kind=SourceKind.FUNCTION_CALL,
                source_id=tool.name,
                description=tool.description,
                origin=SourceOrigin.DECLARED,
            ))
        return manifest

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-safe dict."""
        return {
            "framework": self.framework.value,
            "provider": self.provider.value,
            "provider_model": self.provider_model,
            "context_window": self.context_window,
            "max_output_tokens": self.max_output_tokens,
            "context_strategy": self.context_strategy.value,
            "tools": [
                {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters,
                    "source": t.source,
                }
                for t in self.tools
            ],
            "mcp_servers": list(self.mcp_servers),
            "rag_sources": [s.to_dict() for s in self.rag_sources],
            "long_context_caching": self.long_context_caching,
            "sliding_window_size": self.sliding_window_size,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ApplicationProfile":
        """Restore from a JSON-safe dict."""
        return cls(
            framework=FrameworkKind(data.get("framework", "unknown")),
            provider=ProviderKind(data.get("provider", "unknown")),
            provider_model=data.get("provider_model", ""),
            context_window=data.get("context_window"),
            max_output_tokens=data.get("max_output_tokens"),
            context_strategy=ContextStrategy(data.get("context_strategy", "unknown")),
            tools=[
                ToolInfo(
                    name=t["name"],
                    description=t.get("description", ""),
                    parameters=t.get("parameters", {}),
                    source=t.get("source", "declared"),
                )
                for t in data.get("tools", [])
            ],
            mcp_servers=list(data.get("mcp_servers", [])),
            rag_sources=[
                ContextSource.from_dict(s) for s in data.get("rag_sources", [])
            ],
            long_context_caching=bool(data.get("long_context_caching", False)),
            sliding_window_size=data.get("sliding_window_size"),
            metadata=dict(data.get("metadata", {})),
        )


def detect_framework(messages: list[dict[str, Any]]) -> FrameworkKind:
    """Heuristically detect the framework from message content/structure."""
    if not messages:
        return FrameworkKind.UNKNOWN

    # Look for framework-specific metadata in message dicts.
    for m in messages:
        if not isinstance(m, dict):
            continue
        meta = m.get("metadata") or m.get("additional_kwargs") or {}
        if isinstance(meta, dict):
            keys = " ".join(str(k).lower() for k in meta.keys())
            if "langchain" in keys or "lc_serializable" in keys:
                return FrameworkKind.LANGCHAIN
            if "llamaindex" in keys or "index_id" in keys:
                return FrameworkKind.LLAMAINDEX

    # Tool-call message shapes
    has_tool_calls = any(
        isinstance(m.get("tool_calls"), list) or m.get("role") in {"tool", "function"}
        for m in messages
    )
    if has_tool_calls:
        # OpenAI/Anthropic native shapes are most common
        return FrameworkKind.OPENAI

    return FrameworkKind.UNKNOWN


def detect_context_strategy(messages: list[dict[str, Any]]) -> ContextStrategy:
    """Heuristically detect how the app manages context.

    This is best-effort: we look at message-count patterns, presence of
    summarising system prompts, and explicit metadata.
    """
    if not messages:
        return ContextStrategy.UNKNOWN

    # Explicit metadata wins.
    for m in messages:
        meta = m.get("metadata") or m.get("additional_kwargs") or {}
        if isinstance(meta, dict):
            strategy = str(meta.get("context_strategy", "")).lower()
            if strategy:
                try:
                    return ContextStrategy(strategy)
                except ValueError:
                    pass

    system = " ".join(
        str(m.get("content", "")).lower() for m in messages if m.get("role") == "system"
    )
    if ("summary" in system or "summarize" in system) and "conversation" in system:
        return ContextStrategy.SUMMARIZATION
    if "last" in system and ("messages" in system or "turns" in system):
        return ContextStrategy.SLIDING_WINDOW
    if len(messages) > 20:
        # Very long verbatim history often means full replay or long-context.
        return ContextStrategy.FULL_HISTORY

    return ContextStrategy.UNKNOWN


def build_profile_from_messages(
    messages: list[dict[str, Any]],
    *,
    tools: list[dict[str, Any]] | None = None,
    provider: ProviderKind | None = None,
    context_window: int | None = None,
) -> ApplicationProfile:
    """Derive an application profile from observed messages and tools.

    The derived profile is *observed*, not authoritative.  Use it for
    negotiation and audit, but prefer an explicitly declared profile when
    accuracy matters.
    """
    profile = ApplicationProfile(
        framework=detect_framework(messages),
        context_strategy=detect_context_strategy(messages),
        provider=provider or ProviderKind.UNKNOWN,
        context_window=context_window,
    )

    for tool in tools or []:
        if isinstance(tool, ToolInfo):
            profile.tools.append(tool)
            continue
        if isinstance(tool, dict):
            func = tool.get("function", {}) or tool
            profile.tools.append(ToolInfo(
                name=func.get("name", tool.get("name", "unknown")),
                description=func.get("description", ""),
                parameters=func.get("parameters", func.get("arguments", {})),
                source="derived",
            ))

    # Detect RAG evidence in messages (e.g. retrieved chunks, sources).
    for m in messages:
        meta = m.get("metadata") or {}
        if isinstance(meta, dict):
            sources = meta.get("sources") or meta.get("retrieved_chunks") or []
            if sources:
                profile.context_strategy = ContextStrategy.RAG
                for src in sources:
                    if isinstance(src, dict):
                        profile.rag_sources.append(ContextSource(
                            kind=SourceKind.RAG_RETRIEVAL,
                            source_id=src.get("name", "retrieved_source"),
                            metadata={"snippet": str(src.get("content", ""))[:200]},
                            origin=SourceOrigin.OBSERVED,
                        ))

    return profile
