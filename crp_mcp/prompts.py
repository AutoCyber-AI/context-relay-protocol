# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""MCP prompt templates for common CRP integration and governance tasks."""

from __future__ import annotations

from typing import Any

Message = dict[str, Any]


def _user(text: str) -> Message:
    return {"role": "user", "content": {"type": "text", "text": text}}


def discover_crp() -> list[Message]:
    return [
        _user(
            "Explain CRP (Context Relay Protocol) in one paragraph. Mention that it is a "
            "sidecar governance protocol for AI inference, how it differs from MCP/A2A, "
            "and the simplest integration (OpenAI-compatible base_url swap)."
        )
    ]


def integrate_crp(stack: str = "python-openai") -> list[Message]:
    return [
        _user(
            f"I want to add CRP governance to a {stack} project. Walk me through the "
            "one-line integration first, then show the minimal crp.config.yaml if I need "
            "declarative config. Do not hand-write CRP-* headers; use the SDK."
        )
    ]


def write_safety_policy(goal: str = "balanced governance") -> list[Message]:
    return [
        _user(
            f"Write a CRP-Safety-Policy directive string for a project with this goal: {goal}. "
            "Use only real CRP directives (halt-on, warn-on, require-grounding, block-fabrication, "
            "block-distortion, block-pii, oversight). Explain each directive."
        )
    ]


def context_strategy_for_task(task: str = "write a complete user guide") -> list[Message]:
    return [
        _user(
            f"For this task: '{task}', recommend CRP context settings: mode, depth, retrieval "
            "strategy, and whether continuation is likely. Base the recommendation on CRP-SPEC-031 "
            "and CRP-SPEC-035."
        )
    ]


def audit_ai_calls(codebase_path: str = "./") -> list[Message]:
    return [
        _user(
            f"Audit the codebase at '{codebase_path}' for ungoverned AI/LLM calls. "
            "For each call found, explain how to route it through CRP Gateway or the CRP SDK "
            "so it gains governance, safety, and audit."
        )
    ]


def debug_halt(halt_response: str = "") -> list[Message]:
    return [
        _user(
            "CRP returned an HTTP 451 halt. Here is the response:\n"
            f"{halt_response}\n"
            "Explain why it was halted, which safety policy/directive triggered it, and "
            "the safest way to resolve it (do not suggest bypassing the policy)."
        )
    ]


def migrate_v3_v4() -> list[Message]:
    return [
        _user(
            "I have a CRP v3 integration. Give me a concise migration checklist to v4: "
            "client class, config file, safety helpers, headers, conformance testing."
        )
    ]
