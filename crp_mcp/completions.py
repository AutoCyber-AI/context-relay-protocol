# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""MCP completion handlers for argument autocompletion."""

from __future__ import annotations

from typing import Any

from mcp.types import Completion, PromptReference, ResourceTemplateReference

from crp_mcp.capabilities import (
    CONTEXT_MODES,
    CRP_SCHEMAS,
    CRP_TOPICS,
    DEPTH_LEVELS,
    SAFETY_PROFILES,
    SDK_TASKS,
    STORAGE_BACKENDS,
    SUPPORTED_STACKS,
)
from crp_mcp.corpus import get_corpus


def _filter(values: list[str], partial: str) -> Completion:
    lowered = partial.lower()
    matches = [v for v in values if lowered in v.lower()]
    return Completion(values=matches[:100])


async def handle_completion(ref: Any, argument: Any, context: Any) -> Completion | None:
    """Dispatch completion requests for prompt/resource arguments."""
    name = getattr(argument, "name", None) or argument.get("name", "")
    value = getattr(argument, "value", None) or argument.get("value", "")

    # Resource template completions
    if isinstance(ref, ResourceTemplateReference):
        uri = str(ref.uri)
        if "spec" in uri:
            specs = list(get_corpus().list_specs().keys())
            return _filter(specs, value)
        if "topic" in uri:
            return _filter(list(CRP_TOPICS), value)
        if "schema" in uri:
            return _filter(CRP_SCHEMAS, value)
        if "policy" in uri:
            return _filter(SAFETY_PROFILES, value)
        if "config" in uri:
            return _filter(SAFETY_PROFILES, value)
        if "example" in uri:
            return _filter(SDK_TASKS, value)
        return None

    # Prompt argument completions
    if isinstance(ref, PromptReference):
        prompt_name = ref.name
        if prompt_name == "integrate_crp" and name == "stack":
            return _filter(SUPPORTED_STACKS, value)
        if prompt_name == "write_safety_policy" and name == "goal":
            return _filter(["balanced", "strict", "medical", "financial", "public-facing"], value)
        if prompt_name == "context_strategy_for_task" and name == "task":
            return _filter(
                [
                    "write a complete user guide",
                    "answer a quick factual question",
                    "multi-turn customer support chat",
                    "generate code from a large codebase",
                ],
                value,
            )
        return None

    # Tool argument completions — ref may be a prompt reference for tool args?
    # FastMCP passes tool completions via ref/name; handle generic names.
    if name in {"stack", "target_stack"}:
        return _filter(SUPPORTED_STACKS, value)
    if name in {"profile", "safety_profile"}:
        return _filter(SAFETY_PROFILES, value)
    if name in {"task", "sdk_task"}:
        return _filter(SDK_TASKS, value)
    if name in {"spec_id", "spec"}:
        return _filter(list(get_corpus().list_specs().keys()), value)
    if name in {"topic", "topic_name"}:
        return _filter(list(CRP_TOPICS), value)
    if name in {"schema", "schema_name"}:
        return _filter(CRP_SCHEMAS, value)
    if name in {"context_mode", "mode"}:
        return _filter(CONTEXT_MODES, value)
    if name in {"depth"}:
        return _filter(DEPTH_LEVELS, value)
    if name in {"storage_backend", "backend"}:
        return _filter(STORAGE_BACKENDS, value)

    return None
