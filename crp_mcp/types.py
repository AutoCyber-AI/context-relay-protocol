# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Shared Pydantic models and JSON-result helpers for the CRP MCP server."""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CRPInput(BaseModel):
    """Base input model with strict extra=forbid."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")


class ConfirmMixin(BaseModel):
    """Reusable HITL confirmation flag."""

    confirm: bool = Field(
        default=False,
        description="Set true after the human has explicitly confirmed the action.",
    )


class ResourceLink(BaseModel):
    """Machine-readable link to an MCP resource returned with a tool result."""

    uri: str
    mimeType: str | None = None
    title: str | None = None

    model_config = ConfigDict(extra="allow")


class CRPToolResult(BaseModel):
    """Structured output envelope shared by every CRP MCP tool.

    All tools return this shape (serialised as JSON text for backwards
    compatibility).  The ``data`` field captures tool-specific payload fields as
    extra attributes so existing callers can keep reading ``result["ok"]``,
    ``result["error"]``, etc.
    """

    ok: bool = True
    error: str | None = None
    requires_confirmation: bool | None = None
    configured: bool | None = None
    message: str | None = None
    resource_links: list[ResourceLink] | None = None

    model_config = ConfigDict(extra="allow")


def ok(data: dict[str, Any]) -> str:
    return json.dumps({"ok": True, **data})


def err(message: str, **fields: Any) -> str:
    return json.dumps({"ok": False, "error": message, **fields})


def not_configured(action: str = "hosting_setup") -> dict[str, Any]:
    return {
        "configured": False,
        "ok": True,
        "message": (
            "The hosted CRP MCP server is not configured for account-linked actions. "
            "Set CLERK_ISSUER, CLERK_AUTHORIZED_PARTIES, and CLERK_SECRET_KEY to enable "
            f"{action}."
        ),
        "action": action,
    }


def requires_confirm(action: str, target: str) -> dict[str, Any]:
    return {
        "ok": True,
        "requires_confirmation": True,
        "message": f"{action}: {target}. This action requires explicit human confirmation. Re-call with confirm=true to proceed.",
    }
