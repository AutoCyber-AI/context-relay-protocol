# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Data Plane Extension MCP tools: envelopes, context strategy, cost, continuation."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Annotated, Any

from pydantic import Field

from crp_mcp.capabilities import CONTEXT_MODES, DEPTH_LEVELS
from crp_mcp.corpus import get_corpus
from crp_mcp.types import err, ok


class EnvelopePreviewInput:
    payload_json: str


class ContextStrategyInput:
    task: str
    context_mode: str
    depth: str


class EstimateCostInput:
    payload_json: str


class ContinuationPlanInput:
    task: str
    max_tokens_per_call: int


class BuildSessionInput:
    name: str


async def crp_envelope_preview(
    payload_json: Annotated[
        str,
        Field(description='JSON payload describing the call, e.g. {"task": "summarise", "documents": ["doc1"], "messages": [...]}.', min_length=1, max_length=20000),
    ],
) -> str:
    """Preview the CRP context envelope that would be built for a payload.

    This is a static preview only — no LLM call is made.
    """
    try:
        payload = json.loads(payload_json)
    except json.JSONDecodeError as exc:
        return err(f"Invalid JSON payload: {exc}")
    if not isinstance(payload, dict):
        return err("payload_json must be a JSON object.")

    messages = payload.get("messages", [])
    documents = payload.get("documents", [])
    task = payload.get("task", "complete")
    depth = payload.get("depth", "auto")

    estimated_prompt_tokens = _estimate_tokens(messages, documents)

    envelope: dict[str, Any] = {
        "version": "4.0",
        "envelope_id": f"env-{uuid.uuid4().hex[:12]}",
        "task": task,
        "depth": depth,
        "context_mode": _suggest_mode(task, len(documents)),
        "messages_count": len(messages),
        "documents_count": len(documents),
        "estimated_prompt_tokens": estimated_prompt_tokens,
        "continuation_expected": estimated_prompt_tokens > 4096 or task in {"long_output", "continuation"},
        "safety_policy": payload.get("safety_policy", "default-src 'self'; halt-on CRITICAL"),
        "audit": {"created_at": datetime.now(timezone.utc).isoformat(), "sequence": 0},
    }
    return ok({"preview": envelope})


def _estimate_tokens(messages: list[Any], documents: list[Any]) -> int:
    text_parts: list[str] = []
    for m in messages:
        if isinstance(m, dict):
            text_parts.append(str(m.get("content", "")))
        else:
            text_parts.append(str(m))
    for d in documents:
        text_parts.append(str(d))
    text = "\n".join(text_parts)
    # Very rough token heuristic: ~4 chars per token.
    return max(1, len(text) // 4)


def _suggest_mode(task: str, doc_count: int) -> str:
    task_l = task.lower()
    if doc_count == 0 and "chat" in task_l:
        return "conversation"
    if doc_count > 0 and "chat" in task_l:
        return "hybrid"
    if doc_count > 0:
        return "document"
    return "auto"


async def crp_context_strategy(
    task: Annotated[
        str,
        Field(description="Description of the task, e.g. 'write a complete user guide'.", min_length=1, max_length=500),
    ],
    context_mode: Annotated[
        str,
        Field(default="auto", description="Desired context mode: auto, document, conversation, hybrid, zero-ckf.", max_length=30),
    ] = "auto",
    depth: Annotated[
        str,
        Field(default="auto", description="Desired depth: auto, quick, standard, thorough, exhaustive.", max_length=30),
    ] = "auto",
) -> str:
    """Recommend CRP context settings for a task."""
    if context_mode not in CONTEXT_MODES:
        return err(f"Unknown context_mode '{context_mode}'. Use one of: {', '.join(CONTEXT_MODES)}.")
    if depth not in DEPTH_LEVELS:
        return err(f"Unknown depth '{depth}'. Use one of: {', '.join(DEPTH_LEVELS)}.")

    task_l = task.lower()
    mode = context_mode if context_mode != "auto" else _suggest_mode(task, doc_count=1 if "document" in task_l or "guide" in task_l else 0)
    chosen_depth = depth
    if chosen_depth == "auto":
        if any(k in task_l for k in ("quick", "short", "one-line", "brief")):
            chosen_depth = "quick"
        elif any(k in task_l for k in ("complete", "thorough", "deep", "all")):
            chosen_depth = "thorough"
        else:
            chosen_depth = "standard"

    retrieval = "ckf" if mode in {"document", "hybrid"} else "none"
    continuation = mode in {"document", "hybrid"} and chosen_depth in {"thorough", "exhaustive"}

    corpus = get_corpus()
    specs: list[str] = []
    if corpus.available():
        specs = ["CRP-SPEC-031", "CRP-SPEC-035", "CRP-SPEC-004"]

    return ok(
        {
            "task": task,
            "recommended": {
                "context_mode": mode,
                "depth": chosen_depth,
                "retrieval": retrieval,
                "continuation_expected": continuation,
            },
            "specs": specs,
        }
    )


async def crp_estimate_cost(
    payload_json: Annotated[
        str,
        Field(description='JSON payload with messages, documents, model, and expected output length.', min_length=1, max_length=20000),
    ],
) -> str:
    """Return a rough cost/token estimate for a governed call (no live pricing)."""
    try:
        payload = json.loads(payload_json)
    except json.JSONDecodeError as exc:
        return err(f"Invalid JSON payload: {exc}")
    if not isinstance(payload, dict):
        return err("payload_json must be a JSON object.")

    model = payload.get("model", "gpt-4o-mini")
    prompt_tokens = _estimate_tokens(payload.get("messages", []), payload.get("documents", []))
    output_tokens = int(payload.get("expected_output_tokens", 500))

    # Static price table (USD per 1M tokens) — approximate.
    prices: dict[str, dict[str, float]] = {
        "gpt-4o-mini": {"input": 0.15, "output": 0.60},
        "gpt-4o": {"input": 2.50, "output": 10.0},
        "claude-3-5-sonnet": {"input": 3.0, "output": 15.0},
    }
    price = prices.get(model.lower().split("-")[0], prices["gpt-4o-mini"])
    cost = (prompt_tokens * price["input"] + output_tokens * price["output"]) / 1_000_000

    return ok(
        {
            "model": model,
            "estimated_prompt_tokens": prompt_tokens,
            "estimated_output_tokens": output_tokens,
            "estimated_total_tokens": prompt_tokens + output_tokens,
            "estimated_usd": round(cost, 6),
            "note": "Estimate only; actual cost depends on provider rates and CRP Gateway overhead.",
        }
    )


async def crp_continuation_plan(
    task: Annotated[
        str,
        Field(description="Task that may exceed context/output windows, e.g. 'generate 50-page report'.", min_length=1, max_length=500),
    ],
    max_tokens_per_call: Annotated[
        int,
        Field(default=4096, description="Target max tokens per model call.", ge=256, le=128000),
    ] = 4096,
) -> str:
    """Produce a continuation plan for long-generation tasks."""
    task_l = task.lower()
    pages = 10 if "report" in task_l else 5
    tokens_per_page = 500
    total_tokens = pages * tokens_per_page
    calls = max(1, (total_tokens + max_tokens_per_call - 1) // max_tokens_per_call)

    plan = {
        "task": task,
        "continuation_expected": calls > 1,
        "estimated_total_tokens": total_tokens,
        "max_tokens_per_call": max_tokens_per_call,
        "planned_calls": calls,
        "strategy": [
            "1. Split output into logical sections with stable section IDs.",
            "2. Each call includes a CRP-Continuation-State header with previous section hashes.",
            "3. Gateway stitches sections and validates HMAC chain (SPEC-004).",
            "4. Final response returns complete assembled content + audit URL.",
        ],
        "specs": ["CRP-SPEC-004"],
    }
    return ok(plan)


async def crp_build_session(
    name: Annotated[
        str,
        Field(default="mcp-session", description="Human-readable session name.", max_length=100),
    ] = "mcp-session",
) -> str:
    """Create a local session handle for multi-turn conversation."""
    handle = {
        "session_id": f"ses-{uuid.uuid4().hex[:12]}",
        "name": name,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "active",
        "message_count": 0,
        "storage_backend": "memory",
        "note": "Local session handle only. In hosted mode this is persisted by the CRP Gateway.",
    }
    return ok(handle)
