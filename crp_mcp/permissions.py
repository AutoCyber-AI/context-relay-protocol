# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Tool permissions, input validation, and audit telemetry for the CRP MCP server.

Implements least-privilege access controls and OWASP MCP Top 10 mitigations:

* MCP01  token/secret exposure   – arguments containing secrets are redacted
                                   before any audit log entry is written.
* MCP02  privilege escalation    – role-based allow/deny gates with explicit
                                   deny-lists for state-changing/metered tools.
* MCP05  command injection       – identifier-like arguments are restricted to
                                   a safe character class; no shell execution.
* MCP06  intent-flow subversion  – state-changing tools still require
                                   ``confirm=true`` inside the tool body.
* MCP07  authN/authZ             – hosted mode identity is extracted from the
                                   MCP context; local mode falls back to a
                                   configurable role.
* MCP08  audit/telemetry          – every tool call is logged to
                                   ``CRP_MCP_AUDIT_LOG`` when configured.
* MCP09  shadow servers          – server metadata (website_url, instructions)
                                   is set in ``server.py``.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import time
from typing import Any

import httpx

from crp_mcp.auth import Identity, authenticate

# Tools that change state, spend quota, or enqueue side effects.
_STATE_CHANGING_TOOLS: frozenset[str] = frozenset(
    {
        "crp_create_api_key",
        "crp_test_call",
        "crp_deploy_endpoint",
        "crp_benchmark",
        "crp_scan_repo",
        "crp_comply_repo",
        "crp_safety_checkpoint",
    }
)

# Read-only hosted/onboarding tools (safe to expose to ``user`` role).
_HOSTED_READ_TOOLS: frozenset[str] = frozenset(
    {
        "crp_whoami",
        "crp_get_plan",
        "crp_gateway_status",
        "crp_signup_link",
        "crp_upgrade_link",
        "crp_connect_repo_link",
        "crp_comply_link",
    }
)

# Arguments that are treated as opaque identifiers / external references and
# therefore restricted to a conservative character set.
_IDENTIFIER_FIELDS: frozenset[str] = frozenset(
    {
        "repo_ref",
        "branch",
        "pipeline_id",
        "region",
        "model",
        "dataset",
        "scan_id",
        "analysis_id",
        "baseline_id",
    }
)

# Human-readable names (e.g. API key names) allow spaces and dashes as well.
_NAME_FIELDS: frozenset[str] = frozenset({"name"})

_IDENTIFIER_SAFE_RE = re.compile(r"^[A-Za-z0-9_.:/@-]+$")
_NAME_SAFE_RE = re.compile(r"^[A-Za-z0-9_ \-]+$")

_SECRET_KEY_SUBSTRINGS = ("token", "secret", "password", "api_key", "apikey", "credential")


def _parse_set(env_name: str) -> set[str]:
    value = os.environ.get(env_name, "")
    return {item.strip() for item in value.split(",") if item.strip()}


class ToolPermissionStore:
    """Runtime permission store for CRP MCP tools."""

    def __init__(self, mode: str) -> None:
        self._mode = mode
        self._role = self._resolve_role()
        self._allowlist = _parse_set("CRP_MCP_TOOLS_ALLOW")
        self._denylist = _parse_set("CRP_MCP_TOOLS_DENY")
        self._audit_path = os.environ.get("CRP_MCP_AUDIT_LOG")
        self._audit_forwarder = _AuditForwarder()

    def _resolve_role(self) -> str:
        explicit = os.environ.get("CRP_MCP_ROLE", "").strip().lower()
        if explicit:
            return explicit
        # Least-privilege default for hosted mode; permissive default for local.
        return "user" if self._mode == "hosted" else "admin"

    # ------------------------------------------------------------------
    # Role / permission queries
    # ------------------------------------------------------------------
    def current_role(self) -> str:
        return self._role

    def is_allowed(self, tool_name: str, annotations: dict[str, Any] | None = None) -> bool:
        """Return True if ``tool_name`` may be invoked in the current role."""
        annotations = annotations or {}

        # Allow/deny lists are evaluated first so operators can override roles.
        if self._denylist and tool_name in self._denylist:
            return False
        if self._allowlist and tool_name not in self._allowlist:
            return False

        if self._role == "admin":
            return True

        if self._role == "anonymous":
            # Only the quickstart / discovery tool is exposed without auth.
            return tool_name in {"crp_quickstart"}

        if self._role == "readonly":
            return bool(annotations.get("readOnlyHint"))

        if self._role == "user":
            # Users get all read-only and local builder tools, plus read-only
            # hosted queries.  State-changing / metered tools require admin.
            return tool_name not in _STATE_CHANGING_TOOLS

        # Unknown role defaults to deny.
        return False

    # ------------------------------------------------------------------
    # Input validation
    # ------------------------------------------------------------------
    @staticmethod
    def validate_inputs(arguments: dict[str, Any]) -> None:
        """Validate bound arguments for injection attempts.

        Raises ``ValueError`` with a safe message if a dangerous value is found.
        """
        for key, value in arguments.items():
            if not isinstance(value, str):
                continue

            # Universal guard against null bytes and other control characters
            # that could be used to truncate or confuse parsers.
            if "\x00" in value or any(ord(ch) < 32 and ch not in "\t\n\r" for ch in value):
                raise ValueError(f"Argument '{key}' contains invalid control characters")

            if key in _IDENTIFIER_FIELDS and not _IDENTIFIER_SAFE_RE.match(value):
                raise ValueError(
                    f"Argument '{key}' contains unsafe characters. "
                    "Use only letters, digits, and ./_-:@."
                )

            if key in _NAME_FIELDS and not _NAME_SAFE_RE.match(value):
                raise ValueError(
                    f"Argument '{key}' contains unsafe characters. "
                    "Use only letters, digits, spaces, underscores, and hyphens."
                )

    # ------------------------------------------------------------------
    # Audit telemetry
    # ------------------------------------------------------------------
    def audit(
        self,
        *,
        tool: str,
        role: str,
        user_id: str,
        org_id: str | None,
        allowed: bool,
        args: dict[str, Any],
        outcome: str,
        error: str | None = None,
    ) -> None:
        """Append a sanitised audit record if ``CRP_MCP_AUDIT_LOG`` is set."""
        if not self._audit_path:
            return

        record = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "tool": tool,
            "role": role,
            "user_id": user_id,
            "org_id": org_id,
            "allowed": allowed,
            "outcome": outcome,
            "error": error,
            "args": self.sanitise_args(args),
        }

        try:
            with open(self._audit_path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, sort_keys=True) + "\n")
        except Exception:
            # Audit failures must not break the tool call.  They are surfaced
            # only through stderr so they do not interfere with stdio transport.
            import sys

            print(f"[crp-mcp-audit-error] failed to write audit log: {self._audit_path}", file=sys.stderr)

        # Forward to a centralized CRP audit endpoint if configured.  This is
        # fire-and-forget so a slow/down endpoint cannot block tool execution.
        if self._audit_forwarder.is_configured():
            self._audit_forwarder.send(record)

    @staticmethod
    def sanitise_args(args: dict[str, Any]) -> dict[str, Any]:
        """Return a copy of ``args`` with secrets redacted and long strings trimmed."""
        safe: dict[str, Any] = {}
        for key, value in args.items():
            if isinstance(value, str):
                lowered_key = key.lower()
                if any(sub in lowered_key for sub in _SECRET_KEY_SUBSTRINGS):
                    safe[key] = "***REDACTED***"
                elif len(value) > 500:
                    safe[key] = value[:500] + "...[truncated]"
                else:
                    safe[key] = value
            else:
                safe[key] = value
        return safe


class _AuditForwarder:
    """Send audit records to a centralized CRP audit endpoint.

    Configured via ``CRP_AUDIT_ENDPOINT`` and ``CRP_AUDIT_API_KEY``.  Records
    are sent asynchronously so the MCP tool call is not delayed by network I/O.
    """

    def __init__(self) -> None:
        self._endpoint = os.environ.get("CRP_AUDIT_ENDPOINT", "").rstrip()
        self._api_key = os.environ.get("CRP_AUDIT_API_KEY", "")
        self._client: httpx.AsyncClient | None = None
        self._lock: asyncio.Lock | None = None

    def is_configured(self) -> bool:
        return bool(self._endpoint)

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            headers: dict[str, str] = {"Content-Type": "application/json"}
            if self._api_key:
                headers["Authorization"] = f"Bearer {self._api_key}"
            self._client = httpx.AsyncClient(
                base_url=self._endpoint,
                headers=headers,
                timeout=10.0,
            )
        return self._client

    async def _post(self, record: dict[str, Any]) -> None:
        try:
            await self._get_client().post("/events", json=record)
        except Exception:  # pragma: no cover
            # Forwarding failures must not break the tool call.
            pass

    def send(self, record: dict[str, Any]) -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:  # pragma: no cover
            return
        loop.create_task(self._post(record))


class _MockableAuditForwarder(_AuditForwarder):
    """Subclass used by tests to capture forwarded records."""


class AuditForwarder(_AuditForwarder):
    """Public alias for tests that need to inspect or override forwarding."""


def resolve_identity(ctx: Any) -> Identity:
    """Resolve the caller identity, falling back to a local identity on error."""
    try:
        return authenticate(ctx)
    except Exception:
        return Identity(user_id="local", org_id=None, org_role=None)
