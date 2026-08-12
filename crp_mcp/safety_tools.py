# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Safety Control Plane MCP tools.

These are local, read-only tools that explain, preview, and configure CRP safety
settings.  ``crp_safety_checkpoint`` now supports real review-channel
notifications when hosted mode is configured.
"""

from __future__ import annotations

import json
from typing import Annotated, Any

from pydantic import Field

from crp_mcp.auth import AuthenticationError, HostedNotConfigured, authenticate, hosted_available
from crp_mcp.capabilities import SAFETY_PROFILES
from crp_mcp.checkpoint_policy import CheckpointPolicyError, compile_condition, resolve_route
from crp_mcp.checkpoint_service import (
    approve_checkpoint,
    create_checkpoint,
    reject_checkpoint,
)
from crp_mcp.config_tools import generate_safety_policy
from crp_mcp.resources import get_policy_template
from crp_mcp.types import err, ok, requires_confirm

try:
    from mcp.server.fastmcp import Context
except Exception:  # pragma: no cover
    Context = Any  # type: ignore[misc,assignment]


class SafetyProfileInput:
    profile: str


class SafetySetInput:
    intent_json: str


class SafetyExplainInput:
    key: str


class SafetyCheckpointInput:
    trigger: str
    message: str
    confirm: bool


class SafetyCheckpointWhenInput:
    condition: str
    context_json: str
    route_to: str
    connector: str


class SafetyResolveCheckpointInput:
    checkpoint_id: str
    decision: str
    reviewer: str
    note: str


async def crp_safety_profile(
    profile: Annotated[
        str,
        Field(description="Safety profile: balanced, strict, medical, financial, public.", min_length=1, max_length=30),
    ],
) -> str:
    """Return the policy directive and crp.config.yaml fragment for a safety profile."""
    profile_norm = profile.lower().strip()
    if profile_norm not in SAFETY_PROFILES:
        return err(
            f"Unknown profile '{profile}'. Use one of: {', '.join(SAFETY_PROFILES)}."
        )
    policy = await get_policy_template(profile_norm)
    intent: dict[str, Any] = {"profile": profile_norm}
    if profile_norm == "strict":
        intent.update({"grounding_threshold": 0.85, "halt_on": "HIGH", "pii": "block"})
    elif profile_norm == "medical":
        intent.update({"grounding_threshold": 0.9, "halt_on": "MEDIUM", "pii": "block", "human_oversight": True})
    elif profile_norm == "financial":
        intent.update({"grounding_threshold": 0.85, "halt_on": "HIGH", "pii": "redact", "human_oversight": True})
    elif profile_norm == "public":
        intent.update({"grounding_threshold": 0.75, "halt_on": "CRITICAL", "pii": "redact"})
    else:
        intent.update({"grounding_threshold": 0.7, "halt_on": "CRITICAL", "pii": "flag"})
    config_result = generate_safety_policy(intent)
    return ok(
        {
            "profile": profile_norm,
            "policy_directive": policy,
            "generated_policy": config_result["policy"],
            "notes": config_result["notes"],
        }
    )


async def crp_safety_set(
    intent_json: Annotated[
        str,
        Field(description='JSON object of safety settings, e.g. {"grounding_threshold": 0.85, "halt_on": "HIGH"}.', min_length=1, max_length=5000),
    ],
) -> str:
    """Translate safety settings into a CRP-Safety-Policy directive string."""
    try:
        intent = json.loads(intent_json)
    except json.JSONDecodeError as exc:
        return err(f"Invalid JSON intent: {exc}")
    if not isinstance(intent, dict):
        return err("intent_json must be a JSON object.")
    result = generate_safety_policy(intent)
    return ok(result)


async def crp_safety_show() -> str:
    """Show the default CRP Safety Control Plane capabilities and coverage map."""
    from crp.security.control_plane import get_default_control_plane

    cp = get_default_control_plane()
    return ok(
        {
            "capabilities": [cap.to_dict() for cap in cp.list_capabilities()],
            "out_of_scope": list(cp.coverage.out_of_scope),
        }
    )


async def crp_safety_explain(
    key: Annotated[
        str,
        Field(description="Safety capability key/name to explain, e.g. 'grounding_verification'.", min_length=1, max_length=60),
    ],
) -> str:
    """Explain a single CRP Safety Control Plane capability by key."""
    from crp.security.control_plane import get_default_control_plane

    cp = get_default_control_plane()
    key_norm = key.lower().strip().replace("-", "_")
    for cap in cp.list_capabilities():
        cap_key = cap.name.lower().replace("-", "_")
        if cap_key == key_norm:
            info = cap.to_dict()
            return ok({"key": info["name"], **info})
    return err(
        f"Safety capability '{key}' not found. "
        "Use crp_safety_show to list available capabilities."
    )


async def crp_safety_checkpoint(
    trigger: Annotated[
        str,
        Field(default="RISK_HIGH", description="Checkpoint trigger: RISK_HIGH, HALT, POLICY_VIOLATION, etc.", max_length=60),
    ] = "RISK_HIGH",
    message: Annotated[
        str,
        Field(default="", description="Optional message shown to the human reviewer.", max_length=500),
    ] = "",
    confirm: Annotated[
        bool,
        Field(default=False, description="Set true after the human has explicitly confirmed the action."),
    ] = False,
    ctx: Annotated[
        Context | None,
        Field(default=None, description="MCP request context (injected by FastMCP)."),
    ] = None,
) -> str:
    """Create or preview a human-in-the-loop safety checkpoint.

    Without ``confirm=true`` the tool returns a confirmation prompt.  With
    ``confirm=true`` and hosted mode configured it creates a real checkpoint and
    notifies the configured review channels (console, Slack, email, SMS, etc.).
    """
    if not confirm:
        return ok(
            requires_confirm(
                "Create human-in-the-loop checkpoint",
                f"trigger={trigger}",
            )
        )

    identity = None
    try:
        if hosted_available():
            identity = authenticate(ctx)
    except (HostedNotConfigured, AuthenticationError):
        # Fall back to local preview when auth is unavailable.
        identity = None

    if identity is None:
        return ok(
            {
                "checkpoint_id": "preview-only",
                "trigger": trigger,
                "message": message or "Human approval required before proceeding.",
                "status": "waiting_for_human",
                "note": "Local preview. In hosted mode the checkpoint is sent to the configured review channel.",
            }
        )

    checkpoint = await create_checkpoint(
        trigger=trigger,
        message=message,
        identity=identity,
    )
    return ok(checkpoint)


async def crp_safety_checkpoint_when(
    condition: Annotated[
        str,
        Field(
            description='Policy condition to evaluate, e.g. "risk >= HIGH" or "tool_call == \'approve_loan\' and amount > 1000000".',
            min_length=1,
            max_length=500,
        ),
    ],
    context_json: Annotated[
        str,
        Field(
            description='JSON object used as variable context for the condition, e.g. {"risk": "HIGH", "amount": 1500000}.',
            min_length=1,
            max_length=5000,
        ),
    ],
    route_to: Annotated[
        str,
        Field(default="", description="Optional explicit destination (channel, email, etc.).", max_length=200),
    ] = "",
    connector: Annotated[
        str,
        Field(default="", description="Optional explicit connector name. If omitted, routes via CRP_MCP_CHECKPOINT_ROUTES.", max_length=60),
    ] = "",
) -> str:
    """Evaluate a checkpoint policy condition and resolve the review channel.

    Returns whether the condition matched and which connector/route should handle
    the checkpoint.  This is the Phase-8 policy compiler exposed as an MCP tool.
    """
    try:
        ctx = json.loads(context_json)
    except json.JSONDecodeError as exc:
        return err(f"Invalid context JSON: {exc}")
    if not isinstance(ctx, dict):
        return err("context_json must be a JSON object.")

    try:
        matched = compile_condition(condition)(ctx)
    except CheckpointPolicyError as exc:
        return err(f"Policy error: {exc}")

    resolved_connector, resolved_route = connector, route_to
    if not resolved_connector:
        resolved_connector, resolved_route = resolve_route(
            trigger=ctx.get("trigger", "RISK_HIGH"),
            condition=condition,
            context=ctx,
        )
    if not resolved_connector:
        resolved_connector = "console"

    return ok(
        {
            "condition": condition,
            "matched": matched,
            "connector": resolved_connector,
            "route_to": resolved_route,
            "should_checkpoint": matched,
        }
    )


async def crp_resolve_checkpoint(
    checkpoint_id: Annotated[
        str,
        Field(description="Checkpoint identifier to resolve.", min_length=1, max_length=100),
    ],
    decision: Annotated[
        str,
        Field(description="Decision: approved or rejected.", min_length=1, max_length=20),
    ],
    reviewer: Annotated[
        str,
        Field(description="Identifier of the human reviewer.", min_length=1, max_length=200),
    ],
    note: Annotated[
        str,
        Field(default="", description="Optional note from the reviewer.", max_length=1000),
    ] = "",
) -> str:
    """Resolve a pending checkpoint with an approved/rejected decision.

    Supports multi-approver checkpoints: if ``required_approvers`` > 1, the
    checkpoint stays pending until enough approvals are collected.  Any rejection
    immediately resolves the checkpoint as rejected.
    """
    decision_norm = decision.lower().strip()
    if decision_norm == "approved":
        result = approve_checkpoint(checkpoint_id, reviewer, note or None)
    elif decision_norm == "rejected":
        result = reject_checkpoint(checkpoint_id, reviewer, note or None)
    else:
        return err("decision must be 'approved' or 'rejected'.")

    if not result.get("ok"):
        return err(result.get("error", "resolution_failed"))
    return ok(result)
