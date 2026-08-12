# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""CRPv6 Agent SDK — declarative agents with zero loop code (SPEC-059)."""

from __future__ import annotations

from crp.agent_sdk.agent import Agent, AgentResponse
from crp.agent_sdk.events import AgentEvent, AgentEventKind
from crp.agent_sdk.intent_compiler import compile_tool, compile_tools
from crp.agent_sdk.policy import Policy
from crp.agent_sdk.tool_manifest import (
    CompiledTool,
    ResultEnvelope,
    ToolIntent,
    ToolSpec,
)

__all__ = [
    "Agent",
    "AgentResponse",
    "AgentEvent",
    "AgentEventKind",
    "compile_tool",
    "compile_tools",
    "Policy",
    "CompiledTool",
    "ResultEnvelope",
    "ToolIntent",
    "ToolSpec",
]
