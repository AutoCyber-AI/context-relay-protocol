# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Hosted-mode authentication, entitlement, and per-tenant isolation.

Production verification uses Clerk's session JWT:
  * ``CLERK_ISSUER``                - e.g. https://clerk.crprotocol.io
  * ``CLERK_AUTHORIZED_PARTIES``    - comma/space-separated ``aud``/``azp`` values
  * ``CLERK_SECRET_KEY``            - used for server-side Clerk actions if needed

The token is expected as a Bearer token in the MCP context (set by transport-layer
middleware or passed via ``ctx.request_context.request.headers``).  When Clerk is not
configured the server degrades to safe local fallbacks.
"""

from __future__ import annotations

import functools
import os
from dataclasses import dataclass
from typing import Any

from crp_mcp.billing import get_entitlement

try:
    import jwt
    from jwt import PyJWKClient
except Exception:  # pragma: no cover - PyJWT[crypto] is a required dependency
    jwt = None  # type: ignore[assignment]
    PyJWKClient = None  # type: ignore[assignment,misc]

try:
    from mcp.server.auth.middleware.auth_context import get_access_token
    from mcp.server.auth.provider import AccessToken, TokenVerifier
except Exception:  # pragma: no cover
    get_access_token = None  # type: ignore[assignment]
    AccessToken = None  # type: ignore[assignment,misc]
    TokenVerifier = None  # type: ignore[assignment,misc]


@dataclass(frozen=True)
class Identity:
    user_id: str = ""
    org_id: str | None = None
    org_role: str | None = None


class HostedNotConfigured(Exception):
    """Raised when a hosted tool is called but backend auth is not configured."""


class AuthenticationError(PermissionError):
    """Raised when a Clerk token is missing, malformed, or invalid."""


_NOT_CONFIGURED_DETAIL = (
    "The hosted CRP MCP server is not configured for account-linked actions. "
    "Set CLERK_ISSUER, CLERK_AUTHORIZED_PARTIES, and CLERK_SECRET_KEY to enable "
    "whoami, plan, key minting, test calls, deploy, and benchmarks."
)


# ---------------------------------------------------------------------------
# Configuration helpers
# ---------------------------------------------------------------------------
def hosted_available() -> bool:
    """Return True if the minimal Clerk env is present."""
    return bool(
        os.environ.get("CLERK_ISSUER")
        and os.environ.get("CLERK_AUTHORIZED_PARTIES")
        and os.environ.get("CLERK_SECRET_KEY")
    )


def bypass_auth_allowed() -> bool:
    """Allow local testing of hosted tools without Clerk."""
    return os.environ.get("CRP_MCP_HOSTED_BYPASS_AUTH", "").lower() in {"1", "true", "yes"}


def require_hosted_config() -> None:
    if not hosted_available() and not bypass_auth_allowed():
        raise HostedNotConfigured(_NOT_CONFIGURED_DETAIL)


# ---------------------------------------------------------------------------
# Token extraction
# ---------------------------------------------------------------------------
def _authorized_parties() -> list[str]:
    raw = os.environ.get("CLERK_AUTHORIZED_PARTIES", "")
    return [p.strip() for p in raw.replace(",", " ").split() if p.strip()]


def _extract_bearer_token(ctx: Any) -> str | None:
    """Locate a Bearer token inside the MCP context, if one exists."""
    if isinstance(ctx, str):
        return ctx if ctx.startswith("ey") else None

    if isinstance(ctx, dict):
        for key in ("token", "authorization", "access_token"):
            value = ctx.get(key)
            if isinstance(value, str):
                return _strip_bearer(value)
        return None

    request_context = getattr(ctx, "request_context", None)
    if request_context is not None:
        # 1) Meta progress token is sometimes abused by clients to pass context.
        meta = getattr(request_context, "meta", None)
        if meta is not None:
            for key in ("authorization", "token", "access_token"):
                value = getattr(meta, key, None)
                if isinstance(value, str):
                    return _strip_bearer(value)
            # meta may be a dict in some transports
            if isinstance(meta, dict):
                for key in ("authorization", "token", "access_token"):
                    value = meta.get(key)
                    if isinstance(value, str):
                        return _strip_bearer(value)

        # 2) Underlying HTTP request (Starlette) injected by transport middleware.
        request = getattr(request_context, "request", None)
        if request is not None:
            headers = getattr(request, "headers", None)
            if headers is not None:
                auth = headers.get("authorization") or headers.get("Authorization")
                if isinstance(auth, str):
                    return _strip_bearer(auth)

        # 3) Identity already resolved by middleware and stashed on request state.
        state = getattr(request, "state", None)
        if state is not None:
            token = getattr(state, "crp_access_token", None)
            if isinstance(token, str):
                return _strip_bearer(token)

    return None


def _strip_bearer(value: str) -> str | None:
    value = value.strip()
    if value.lower().startswith("bearer "):
        value = value[7:].strip()
    return value if value.startswith("ey") else None


# ---------------------------------------------------------------------------
# JWT verification
# ---------------------------------------------------------------------------
@functools.lru_cache(maxsize=4)
def _jwks_client(issuer: str) -> Any:
    if PyJWKClient is None:  # pragma: no cover
        raise AuthenticationError("PyJWT is not installed")
    jwks_uri = issuer.rstrip("/") + "/.well-known/jwks.json"
    return PyJWKClient(jwks_uri, cache_keys=True)


def _verify_token(token: str) -> dict[str, Any]:
    """Verify a Clerk session JWT and return its claims."""
    if jwt is None:  # pragma: no cover
        raise AuthenticationError("PyJWT is not installed")

    issuer = os.environ.get("CLERK_ISSUER", "").rstrip("/")
    audiences = _authorized_parties()
    if not issuer:
        raise AuthenticationError("CLERK_ISSUER is not configured")
    if not audiences:
        raise AuthenticationError("CLERK_AUTHORIZED_PARTIES is not configured")

    try:
        signing_key = _jwks_client(issuer).get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=audiences,
            issuer=issuer,
        )
    except jwt.ExpiredSignatureError as exc:
        raise AuthenticationError("token_expired") from exc
    except jwt.InvalidAudienceError as exc:
        raise AuthenticationError("token_invalid_audience") from exc
    except jwt.InvalidIssuerError as exc:
        raise AuthenticationError("token_invalid_issuer") from exc
    except jwt.InvalidTokenError as exc:
        raise AuthenticationError(f"token_invalid: {exc}") from exc
    except Exception as exc:
        raise AuthenticationError(f"token_verification_failed: {exc}") from exc

    return claims


def _identity_from_claims(claims: dict[str, Any]) -> Identity:
    """Map Clerk-style claims to an Identity.

    Clerk session tokens contain ``sub`` (user id) and may contain
    ``org_id`` / ``organization_id`` and ``org_role`` / ``org_slug``.
    """
    user_id = str(claims.get("sub", ""))
    if not user_id:
        raise AuthenticationError("token_missing_sub")

    org_id = claims.get("org_id") or claims.get("organization_id")
    if org_id is not None:
        org_id = str(org_id)

    org_role = claims.get("org_role") or claims.get("role")
    if org_role is not None:
        org_role = str(org_role).lower()

    return Identity(user_id=user_id, org_id=org_id, org_role=org_role)


# ---------------------------------------------------------------------------
# Public auth API
# ---------------------------------------------------------------------------
def authenticate(ctx: Any) -> Identity:
    """Verify the Clerk session token supplied in the MCP request context.

    If Clerk is not configured but ``CRP_MCP_HOSTED_BYPASS_AUTH`` is set, return a
    stub identity for local testing.  If a token is missing or invalid, raise
    ``AuthenticationError``.
    """
    require_hosted_config()

    if bypass_auth_allowed() and not hosted_available():
        return Identity(user_id="bypass-user", org_id="bypass-org", org_role="admin")

    if not hosted_available():
        # Already handled by require_hosted_config when bypass is disallowed, but
        # keep explicit for clarity.
        raise HostedNotConfigured(_NOT_CONFIGURED_DETAIL)

    # If the FastMCP auth middleware already verified the token, reuse it —
    # re-derive claims from the retained raw token (AccessToken has no
    # `claims`/`subject` field to carry them directly; see ClerkTokenVerifier).
    access_token = _get_access_token_from_context()
    if access_token is not None and access_token.token:
        claims = _verify_token(access_token.token)
        return _identity_from_claims(claims)

    token = _extract_bearer_token(ctx)
    if not token:
        raise AuthenticationError("missing_authorization")

    claims = _verify_token(token)
    return _identity_from_claims(claims)


def _get_access_token_from_context() -> Any:
    if get_access_token is None:
        return None
    try:
        return get_access_token()
    except LookupError:
        return None


async def require_feature(identity: Identity, product: str, feature: str) -> dict[str, Any]:
    """Raise ``PermissionError`` if the identity lacks a product feature."""
    ent = await get_entitlement(identity, product)
    if feature in ent.get("features", []):
        return ent
    raise PermissionError(f"upgrade_required:{product}:{feature}")


def tenant_api_key(identity: Identity | None = None) -> str | None:
    """Resolve a tenant-scoped Gateway API key for live calls.

    Production: fetch from a secure token service keyed by ``identity.org_id``.
    Local harness: ``CRP_HOSTED_API_KEY`` env var.
    """
    return os.environ.get("CRP_HOSTED_API_KEY")


def gateway_url() -> str:
    return os.environ.get("CRP_GATEWAY_URL", "https://gateway.crprotocol.io/v1")


def comply_base_url() -> str:
    return os.environ.get("CRP_COMPLY_BASE_URL", "https://comply.crprotocol.io")


def public_origin() -> str:
    return os.environ.get("CRP_PUBLIC_ORIGIN", "https://crprotocol.io")


def audit_url() -> str | None:
    return os.environ.get("CRP_AUDIT_ENDPOINT")


# ---------------------------------------------------------------------------
# FastMCP token verifier
# ---------------------------------------------------------------------------
class ClerkTokenVerifier:
    """TokenVerifier implementation for FastMCP's built-in auth middleware.

    Verifies Clerk session JWTs and returns an ``AccessToken`` so FastMCP can
    enforce Bearer authentication at the HTTP transport layer.
    """

    async def verify_token(self, token: str) -> Any:
        import asyncio

        if jwt is None:  # pragma: no cover
            return None
        try:
            # JWKS fetch is synchronous and may hit the network; run it in a
            # thread so the async HTTP transport is not blocked.
            claims = await asyncio.to_thread(_verify_token, token)
        except AuthenticationError:
            return None

        scopes: list[str] = []
        if "scope" in claims and isinstance(claims["scope"], str):
            scopes = [s.strip() for s in claims["scope"].split() if s.strip()]
        # Fall back to sensible CRP scopes if none are present in the token.
        if not scopes:
            scopes = ["crp:gateway", "crp:comply", "crp:scan"]

        if AccessToken is None:  # pragma: no cover
            return None
        # Note: the mcp SDK's AccessToken model only has token/client_id/scopes/
        # expires_at/resource fields — there is no place to attach the verified
        # claims dict or a "subject" field directly. The raw bearer token is
        # retained in `token`; callers that need claims re-verify via
        # `_verify_token(access_token.token)` (cheap: JWKS client is cached).
        return AccessToken(
            token=token,
            client_id=str(claims.get("sub", "")) or "clerk",
            scopes=scopes,
        )
