# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Tests for CRP MCP hosted authentication."""

from __future__ import annotations

import os
from types import SimpleNamespace
from typing import Any

import pytest

from crp_mcp import auth
from crp_mcp.auth import (
    AuthenticationError,
    HostedNotConfigured,
    Identity,
    authenticate,
    hosted_available,
    require_feature,
)


@pytest.fixture(autouse=True)
def _clear_auth_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in (
        "CLERK_ISSUER",
        "CLERK_AUTHORIZED_PARTIES",
        "CLERK_SECRET_KEY",
        "CRP_MCP_HOSTED_BYPASS_AUTH",
    ):
        monkeypatch.delenv(key, raising=False)
    auth._jwks_client.cache_clear()


@pytest.mark.asyncio
async def test_hosted_not_configured_raises() -> None:
    with pytest.raises(HostedNotConfigured):
        authenticate(None)


@pytest.mark.asyncio
async def test_bypass_auth_without_clerk(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CRP_MCP_HOSTED_BYPASS_AUTH", "1")
    identity = authenticate(None)
    assert identity.org_role == "admin"


@pytest.mark.asyncio
async def test_authenticate_requires_token_when_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CLERK_ISSUER", "https://clerk.example.com")
    monkeypatch.setenv("CLERK_AUTHORIZED_PARTIES", "https://crprotocol.io")
    monkeypatch.setenv("CLERK_SECRET_KEY", "sk_test_xxx")

    with pytest.raises(AuthenticationError, match="missing_authorization"):
        authenticate(None)


@pytest.mark.asyncio
async def test_authenticate_accepts_valid_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CLERK_ISSUER", "https://clerk.example.com")
    monkeypatch.setenv("CLERK_AUTHORIZED_PARTIES", "https://crprotocol.io")
    monkeypatch.setenv("CLERK_SECRET_KEY", "sk_test_xxx")

    def _fake_verify(token: str) -> dict[str, Any]:
        assert token == "eyJfake"
        return {
            "sub": "user_123",
            "org_id": "org_456",
            "org_role": "admin",
        }

    monkeypatch.setattr(auth, "_verify_token", _fake_verify)

    identity = authenticate("eyJfake")
    assert identity == Identity(user_id="user_123", org_id="org_456", org_role="admin")


@pytest.mark.asyncio
async def test_extract_bearer_token_from_context_headers() -> None:
    request = SimpleNamespace(
        headers={"authorization": "Bearer eyJfromheader"},
        state=SimpleNamespace(),
    )
    request_context = SimpleNamespace(
        meta=None,
        request=request,
    )
    ctx = SimpleNamespace(request_context=request_context)
    assert auth._extract_bearer_token(ctx) == "eyJfromheader"


@pytest.mark.asyncio
async def test_extract_bearer_token_from_dict() -> None:
    assert auth._extract_bearer_token({"token": "eyJdict"}) == "eyJdict"
    assert auth._extract_bearer_token({"authorization": "Bearer eyJdict"}) == "eyJdict"


@pytest.mark.asyncio
async def test_strip_bearer_rejects_non_jwt() -> None:
    assert auth._strip_bearer("Basic abc") is None
    assert auth._strip_bearer("notatoken") is None


@pytest.mark.asyncio
async def test_require_feature_free_tier_denies_state_change() -> None:
    identity = Identity(user_id="u", org_id="o", org_role="user")
    with pytest.raises(PermissionError, match="upgrade_required"):
        await require_feature(identity, "gateway", "deploy_endpoint")


def test_hosted_available_requires_all_three() -> None:
    assert hosted_available() is False


def test_server_enables_fastmcp_auth_in_hosted_mode() -> None:
    import subprocess
    import sys

    env = os.environ.copy()
    env["CRP_MCP_MODE"] = "hosted"
    env["CLERK_ISSUER"] = "https://clerk.example.com"
    env["CLERK_AUTHORIZED_PARTIES"] = "https://crprotocol.io"
    env["CLERK_SECRET_KEY"] = "sk_test_xxx"

    script = (
        "from crp_mcp.server import mcp; "
        "print('auth=' + ('yes' if mcp.settings.auth else 'no'))"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "auth=yes" in result.stdout


@pytest.mark.asyncio
async def test_clerk_token_verifier_returns_access_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CLERK_ISSUER", "https://clerk.example.com")
    monkeypatch.setenv("CLERK_AUTHORIZED_PARTIES", "https://crprotocol.io")
    monkeypatch.setenv("CLERK_SECRET_KEY", "sk_test_xxx")

    def _fake_verify(token: str) -> dict[str, Any]:
        return {
            "sub": "user_123",
            "org_id": "org_456",
            "org_role": "admin",
            "scope": "crp:gateway crp:comply",
        }

    monkeypatch.setattr(auth, "_verify_token", _fake_verify)

    verifier = auth.ClerkTokenVerifier()
    access_token = await verifier.verify_token("eyJfake")
    assert access_token is not None
    # AccessToken (mcp SDK) only has token/client_id/scopes/expires_at/resource —
    # no subject/claims field. The user id is carried via client_id, and the
    # raw token is retained so callers can re-verify to recover full claims.
    assert access_token.token == "eyJfake"
    assert access_token.client_id == "user_123"
    assert "crp:gateway" in access_token.scopes


@pytest.mark.asyncio
async def test_authenticate_reuses_fastmcp_access_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """authenticate() should recover identity from a FastMCP-verified AccessToken.

    Regression test: access_token.claims does not exist on the real mcp SDK's
    AccessToken model, so authenticate() must re-verify via access_token.token
    instead of crashing with AttributeError.
    """
    from mcp.server.auth.provider import AccessToken

    monkeypatch.setenv("CLERK_ISSUER", "https://clerk.example.com")
    monkeypatch.setenv("CLERK_AUTHORIZED_PARTIES", "https://crprotocol.io")
    monkeypatch.setenv("CLERK_SECRET_KEY", "sk_test_xxx")

    def _fake_verify(token: str) -> dict[str, Any]:
        assert token == "eyJfake"
        return {"sub": "user_123", "org_id": "org_456", "org_role": "admin"}

    monkeypatch.setattr(auth, "_verify_token", _fake_verify)
    monkeypatch.setattr(
        auth,
        "_get_access_token_from_context",
        lambda: AccessToken(token="eyJfake", client_id="user_123", scopes=["crp:gateway"]),
    )

    identity = auth.authenticate({})
    assert identity.user_id == "user_123"
    assert identity.org_id == "org_456"
    assert identity.org_role == "admin"


@pytest.mark.asyncio
async def test_clerk_token_verifier_rejects_invalid_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CLERK_ISSUER", "https://clerk.example.com")
    monkeypatch.setenv("CLERK_AUTHORIZED_PARTIES", "https://crprotocol.io")
    monkeypatch.setenv("CLERK_SECRET_KEY", "sk_test_xxx")

    def _fake_verify(token: str) -> dict[str, Any]:
        raise AuthenticationError("token_invalid")

    monkeypatch.setattr(auth, "_verify_token", _fake_verify)

    verifier = auth.ClerkTokenVerifier()
    assert await verifier.verify_token("bad") is None
