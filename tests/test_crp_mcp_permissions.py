# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Permission, audit, input validation, and structured-output tests for the CRP MCP server."""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any

import pytest

from crp_mcp.permissions import AuditForwarder, ToolPermissionStore
from crp_mcp.server import mcp


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _tool_text(result: Any) -> str:
    content, _meta = result
    return content[0].text


@pytest.fixture
def clear_role_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove role-related env vars before each test."""
    for key in (
        "CRP_MCP_ROLE",
        "CRP_MCP_TOOLS_ALLOW",
        "CRP_MCP_TOOLS_DENY",
        "CRP_MCP_AUDIT_LOG",
        "CRP_AUDIT_ENDPOINT",
        "CRP_AUDIT_API_KEY",
    ):
        monkeypatch.delenv(key, raising=False)


# ---------------------------------------------------------------------------
# Role-based access control
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_default_local_role_allows_all(clear_role_env: None) -> None:
    store = ToolPermissionStore(mode="local")
    assert store.current_role() == "admin"
    assert store.is_allowed("crp_create_api_key", {"readOnlyHint": False})
    assert store.is_allowed("crp_explain", {"readOnlyHint": True})


@pytest.mark.asyncio
async def test_hosted_default_role_is_user(clear_role_env: None) -> None:
    store = ToolPermissionStore(mode="hosted")
    assert store.current_role() == "user"
    assert store.is_allowed("crp_explain", {"readOnlyHint": True})
    assert not store.is_allowed("crp_create_api_key", {"readOnlyHint": False})


@pytest.mark.asyncio
async def test_readonly_role_allows_only_readonly_tools(clear_role_env: None) -> None:
    store = ToolPermissionStore(mode="local")
    # Force role by manipulating internal state for unit test.
    store._role = "readonly"
    assert store.is_allowed("crp_explain", {"readOnlyHint": True})
    assert not store.is_allowed("crp_create_api_key", {"readOnlyHint": False})
    assert not store.is_allowed("crp_scan_repo", {"readOnlyHint": False})


@pytest.mark.asyncio
async def test_anonymous_role_only_quickstart(clear_role_env: None) -> None:
    store = ToolPermissionStore(mode="local")
    store._role = "anonymous"
    assert store.is_allowed("crp_quickstart", {})
    assert not store.is_allowed("crp_explain", {"readOnlyHint": True})


@pytest.mark.asyncio
async def test_user_role_denies_state_changing_tools(clear_role_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CRP_MCP_ROLE", "user")
    result = await mcp.call_tool("crp_create_api_key", {})
    data = json.loads(_tool_text(result))
    assert data["ok"] is False
    assert "permission_denied" in data["error"]


@pytest.mark.asyncio
async def test_admin_role_allows_state_changing_tools(clear_role_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CRP_MCP_ROLE", "admin")
    monkeypatch.setenv("CRP_MCP_HOSTED_BYPASS_AUTH", "1")
    # Without confirm the tool asks for confirmation, which proves it was allowed through.
    result = await mcp.call_tool("crp_create_api_key", {})
    data = json.loads(_tool_text(result))
    assert data["ok"] is True
    assert data.get("requires_confirmation") is True


# ---------------------------------------------------------------------------
# Allow/deny list overrides
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_deny_list_blocks_tool(clear_role_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CRP_MCP_TOOLS_DENY", "crp_explain")
    result = await mcp.call_tool("crp_explain", {"topic": "grounding"})
    data = json.loads(_tool_text(result))
    assert data["ok"] is False
    assert "permission_denied" in data["error"]


@pytest.mark.asyncio
async def test_allow_list_restricts_tools(clear_role_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CRP_MCP_TOOLS_ALLOW", "crp_quickstart,crp_explain")
    explain = await mcp.call_tool("crp_explain", {"topic": "grounding"})
    assert json.loads(_tool_text(explain))["ok"] is True

    compare = await mcp.call_tool("crp_compare", {"against": "MCP"})
    data = json.loads(_tool_text(compare))
    assert data["ok"] is False
    assert "permission_denied" in data["error"]


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_input_validation_rejects_shell_metacharacters(clear_role_env: None) -> None:
    result = await mcp.call_tool("crp_scan_repo", {"repo_ref": "owner/repo; rm -rf /"})
    data = json.loads(_tool_text(result))
    assert data["ok"] is False
    assert "input_validation_failed" in data["error"]


@pytest.mark.asyncio
async def test_input_validation_rejects_null_bytes(clear_role_env: None) -> None:
    result = await mcp.call_tool("crp_explain", {"topic": "grounding\x00"})
    data = json.loads(_tool_text(result))
    assert data["ok"] is False
    assert "input_validation_failed" in data["error"]


# ---------------------------------------------------------------------------
# Audit telemetry
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_audit_log_writes_and_redacts_secrets(
    clear_role_env: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    log_path = tmp_path / "audit.jsonl"
    monkeypatch.setenv("CRP_MCP_AUDIT_LOG", str(log_path))
    # Re-create the server permission store by reimporting is hard; instead call audit directly.
    store = ToolPermissionStore(mode="local")
    store._audit_path = str(log_path)
    store.audit(
        tool="crp_create_api_key",
        role="admin",
        user_id="test-user",
        org_id="test-org",
        allowed=True,
        args={"name": "my-key", "api_key": "sk-secret"},
        outcome="success",
    )
    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["tool"] == "crp_create_api_key"
    assert record["args"]["api_key"] == "***REDACTED***"
    assert record["args"]["name"] == "my-key"


class _FakeAsyncClient:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.posts: list[tuple[str, dict[str, Any] | None]] = []

    async def post(self, path: str, json: dict[str, Any] | None = None) -> None:
        self.posts.append((path, json))


@pytest.mark.asyncio
async def test_audit_forwarder_sends_to_endpoint(
    clear_role_env: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    log_path = tmp_path / "audit.jsonl"
    monkeypatch.setenv("CRP_MCP_AUDIT_LOG", str(log_path))
    monkeypatch.setenv("CRP_AUDIT_ENDPOINT", "https://audit.crprotocol.io")
    monkeypatch.setenv("CRP_AUDIT_API_KEY", "test-api-key")

    store = ToolPermissionStore(mode="local")
    fake = _FakeAsyncClient()
    store._audit_forwarder._client = fake

    store.audit(
        tool="crp_create_api_key",
        role="admin",
        user_id="test-user",
        org_id="test-org",
        allowed=True,
        args={"name": "my-key"},
        outcome="success",
    )
    # Give the fire-and-forget task a chance to run.
    await asyncio.sleep(0.05)

    assert len(fake.posts) == 1
    path, payload = fake.posts[0]
    assert path == "/events"
    assert payload is not None
    assert payload["tool"] == "crp_create_api_key"
    assert payload["args"]["name"] == "my-key"


@pytest.mark.asyncio
async def test_audit_forwarder_skipped_when_not_configured(
    clear_role_env: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    log_path = tmp_path / "audit.jsonl"
    monkeypatch.setenv("CRP_MCP_AUDIT_LOG", str(log_path))
    # No CRP_AUDIT_ENDPOINT set.

    store = ToolPermissionStore(mode="local")
    fake = _FakeAsyncClient()
    store._audit_forwarder._client = fake

    store.audit(
        tool="crp_explain",
        role="user",
        user_id="test-user",
        org_id="test-org",
        allowed=True,
        args={"topic": "grounding"},
        outcome="success",
    )
    await asyncio.sleep(0.05)
    assert len(fake.posts) == 0


# ---------------------------------------------------------------------------
# Structured output / spec compliance
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_tools_advertise_output_schema(clear_role_env: None) -> None:
    tools = await mcp.list_tools()
    by_name = {t.name: t for t in tools}
    assert "crp_explain" in by_name
    assert by_name["crp_explain"].outputSchema is not None
    assert "ok" in by_name["crp_explain"].outputSchema.get("properties", {})


@pytest.mark.asyncio
async def test_tool_call_returns_structured_content(clear_role_env: None) -> None:
    content, structured = await mcp.call_tool("crp_quickstart", {})
    assert content
    data = json.loads(content[0].text)
    assert data["ok"] is True
    assert structured is not None
    assert structured["ok"] is True


# ---------------------------------------------------------------------------
# OAuth resource server metadata
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_tool_result_includes_resource_links(clear_role_env: None) -> None:
    content, structured = await mcp.call_tool("crp_read_spec", {"spec_id": "CRP-SPEC-001"})
    assert structured is not None
    links = structured.get("resource_links") or []
    assert any("crp://spec/CRP-SPEC-001" in link.get("uri", "") for link in links)


@pytest.mark.asyncio
async def test_oauth_authorization_server_resource(clear_role_env: None) -> None:
    result = await mcp.read_resource("crp://.well-known/oauth-authorization-server")
    text = result[0].content
    data = json.loads(text)
    assert "issuer" in data
    assert "authorization_endpoint" in data


@pytest.mark.asyncio
async def test_oauth_resource_server_resource(clear_role_env: None) -> None:
    result = await mcp.read_resource("crp://.well-known/oauth-resource-server")
    text = result[0].content
    data = json.loads(text)
    assert "resource" in data
    assert "scopes_supported" in data
