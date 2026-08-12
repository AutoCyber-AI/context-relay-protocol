# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Hosted-mode CRP Gateway tools: account, billing, deployment, metered calls.

All state-changing tools use auth + entitlement + explicit ``confirm=true`` HITL.
Read-only redirect tools degrade gracefully when Clerk/Stripe are not configured.
"""

from __future__ import annotations

from typing import Annotated, Any

from pydantic import Field

from crp_mcp.auth import (
    AuthenticationError,
    HostedNotConfigured,
    authenticate,
    bypass_auth_allowed,
    gateway_url,
    hosted_available,
    require_feature,
    tenant_api_key,
)
from crp_mcp.backend_client import BackendError, BackendNotConfigured, GatewayClient
from crp_mcp.billing import create_checkout_session, format_upgrade_result
from crp_mcp.types import err, not_configured, ok, requires_confirm

try:
    from mcp.server.fastmcp import Context
except Exception:  # pragma: no cover
    Context = Any  # type: ignore[misc,assignment]


class WhoamiInput:
    pass


class GetPlanInput:
    product: str


class ProductPlanInput:
    product: str
    plan: str


class CreateApiKeyInput:
    name: str
    confirm: bool


class TestCallInput:
    message: str
    model: str
    confirm: bool


class DeployInput:
    pipeline_id: str
    region: str
    confirm: bool


class BenchmarkInput:
    dataset: str
    confirm: bool


# ---------------------------------------------------------------------------
# Redirect-only onboarding helpers
# ---------------------------------------------------------------------------
async def crp_signup_link() -> str:
    """Return a signup URL for the human to open in their browser."""
    return ok(
        {
            "action": "open_in_browser",
            "url": "https://crprotocol.io/sign-up",
            "message": "Open this to create your CRP account. Continue once signed in.",
        }
    )


async def crp_upgrade_link(
    ctx: Context,
    product: Annotated[
        str,
        Field(description="'gateway' | 'comply' | 'scan'", min_length=1, max_length=30),
    ],
    plan: Annotated[
        str,
        Field(description="e.g. 'starter', 'scale', 'team', 'pro'", min_length=1, max_length=60),
    ],
) -> str:
    """Return the Stripe Checkout URL for the chosen plan."""
    try:
        identity = authenticate(ctx)
    except HostedNotConfigured:
        return ok(not_configured("upgrade"))
    except AuthenticationError as exc:
        return err(f"authentication_failed: {exc}")

    result = await create_checkout_session(identity, product, plan)
    return format_upgrade_result(result)


async def crp_connect_repo_link(ctx: Context) -> str:
    """Return the GitHub App install URL."""
    try:
        authenticate(ctx)
    except HostedNotConfigured:
        return ok(not_configured("connect_repo"))
    except AuthenticationError as exc:
        return err(f"authentication_failed: {exc}")
    return ok(
        {
            "action": "open_in_browser",
            "url": "https://github.com/apps/crp-comply/installations/new",
            "message": "Install the CRP GitHub App in your browser.",
        }
    )


# ---------------------------------------------------------------------------
# Authenticated read/account tools
# ---------------------------------------------------------------------------
async def crp_whoami(ctx: Context) -> str:
    """Report the signed-in user's products/plans/quotas."""
    from crp_mcp.billing import get_entitlement

    try:
        identity = authenticate(ctx)
    except HostedNotConfigured:
        return ok(not_configured("whoami"))
    except AuthenticationError as exc:
        return err(f"authentication_failed: {exc}")

    gateway_ent = await get_entitlement(identity, "gateway")
    return ok(
        {
            "user_id": identity.user_id,
            "org_id": identity.org_id,
            "org_role": identity.org_role,
            "configured": hosted_available(),
            "bypass_auth": bypass_auth_allowed(),
            "gateway_plan": gateway_ent.get("plan"),
            "gateway_features": gateway_ent.get("features"),
        }
    )


async def crp_get_plan(
    ctx: Context,
    product: Annotated[
        str,
        Field(default="gateway", description="'gateway' | 'comply' | 'scan'", max_length=30),
    ] = "gateway",
) -> str:
    """Return current Gateway/Comply/Scan plan + remaining quota."""
    try:
        identity = authenticate(ctx)
    except HostedNotConfigured:
        return ok(not_configured("view_plan"))
    except AuthenticationError as exc:
        return err(f"authentication_failed: {exc}")
    try:
        ent = await require_feature(identity, product, "view_plan")
    except PermissionError as exc:
        return err(str(exc))
    return ok(
        {
            "product": product,
            "plan": ent.get("plan"),
            "features": ent.get("features"),
            "quota": ent.get("quota"),
            "configured": hosted_available(),
        }
    )


async def crp_gateway_status() -> str:
    """Report whether the hosted CRP Gateway backend is configured."""
    return ok(
        {
            "configured": hosted_available(),
            "bypass_auth_allowed": bypass_auth_allowed(),
            "gateway_url": gateway_url(),
            "tenant_api_key_present": bool(tenant_api_key(None)),
        }
    )


# ---------------------------------------------------------------------------
# State-changing / metered tools
# ---------------------------------------------------------------------------
async def crp_create_api_key(
    ctx: Context,
    name: Annotated[
        str,
        Field(default="mcp-generated-key", description="Human-readable name for the API key.", max_length=100),
    ] = "mcp-generated-key",
    confirm: Annotated[
        bool,
        Field(default=False, description="Set true after the human has explicitly confirmed the action."),
    ] = False,
) -> str:
    """Mint a scoped, revocable Gateway API key. Requires auth + human confirmation."""
    try:
        identity = authenticate(ctx)
    except HostedNotConfigured:
        return ok(not_configured("create_api_key"))
    except AuthenticationError as exc:
        return err(f"authentication_failed: {exc}")
    if not confirm:
        return ok(
            requires_confirm(
                "Create Gateway API key",
                f"name={name}",
            )
        )
    try:
        await require_feature(identity, "gateway", "create_api_key")
    except PermissionError as exc:
        return err(str(exc))

    client = GatewayClient()
    try:
        result = await client.create_api_key(name)
        return ok(
            {
                "api_key": result.get("key", result.get("api_key", "created")),
                "name": name,
                "live": True,
            }
        )
    except (BackendNotConfigured, BackendError):
        return ok(
            {
                "api_key": "crp_gw_stub_DO_NOT_USE",
                "name": name,
                "live": False,
                "message": "Gateway backend unavailable; returning stub key.",
            }
        )


async def crp_test_call(
    ctx: Context,
    message: Annotated[
        str,
        Field(default="Hello, CRP", description="User message for the test call.", max_length=500),
    ] = "Hello, CRP",
    model: Annotated[
        str,
        Field(default="gpt-4o-mini", description="Model to use for the test call.", max_length=60),
    ] = "gpt-4o-mini",
    confirm: Annotated[
        bool,
        Field(default=False, description="Set true after the human has explicitly confirmed the action."),
    ] = False,
) -> str:
    """Run ONE real governed call and return the governance panel."""
    try:
        identity = authenticate(ctx)
    except HostedNotConfigured:
        return ok(not_configured("test_call"))
    except AuthenticationError as exc:
        return err(f"authentication_failed: {exc}")
    if not confirm:
        return ok(
            requires_confirm(
                "Run real governed call",
                f"message='{message}', model={model}",
            )
        )
    try:
        await require_feature(identity, "gateway", "test_call")
    except PermissionError as exc:
        return err(str(exc))

    client = GatewayClient()
    try:
        result = await client.test_call(message, model)
        return ok({"live": True, **result})
    except (BackendNotConfigured, BackendError):
        return ok(
            {
                "live": False,
                "message": "Gateway backend unavailable; returning stub.",
                "input": message,
                "model": model,
            }
        )


async def crp_deploy_endpoint(
    ctx: Context,
    pipeline_id: Annotated[
        str,
        Field(description="The id of a built pipeline to deploy.", min_length=1, max_length=100),
    ],
    region: Annotated[
        str,
        Field(default="us-east", description="Deployment region.", max_length=30),
    ] = "us-east",
    confirm: Annotated[
        bool,
        Field(default=False, description="Set true after the human has explicitly confirmed the action."),
    ] = False,
) -> str:
    """Deploy a built pipeline as a LIVE production endpoint."""
    try:
        identity = authenticate(ctx)
    except HostedNotConfigured:
        return ok(not_configured("deploy_endpoint"))
    except AuthenticationError as exc:
        return err(f"authentication_failed: {exc}")
    if not confirm:
        return ok(
            requires_confirm(
                "Deploy pipeline as live endpoint",
                f"pipeline_id={pipeline_id}, region={region}",
            )
        )
    try:
        await require_feature(identity, "gateway", "deploy_endpoint")
    except PermissionError as exc:
        return err(str(exc))

    client = GatewayClient()
    try:
        result = await client.deploy_endpoint(pipeline_id, region)
        return ok(
            {
                "live": True,
                "endpoint_url": result.get("endpoint_url", result.get("url")),
                "region": region,
                **result,
            }
        )
    except (BackendNotConfigured, BackendError):
        return ok(
            {
                "live": False,
                "endpoint_url": f"https://gateway.crprotocol.io/stub/{pipeline_id}",
                "region": region,
                "message": "Gateway backend unavailable; returning stub endpoint.",
            }
        )


async def crp_benchmark(
    ctx: Context,
    dataset: Annotated[
        str,
        Field(default="default", description="Benchmark dataset name or identifier.", max_length=100),
    ] = "default",
    confirm: Annotated[
        bool,
        Field(default=False, description="Set true after the human has explicitly confirmed the action."),
    ] = False,
) -> str:
    """Run an SQB-style quality check. Metered against the user's plan."""
    try:
        identity = authenticate(ctx)
    except HostedNotConfigured:
        return ok(not_configured("benchmark"))
    except AuthenticationError as exc:
        return err(f"authentication_failed: {exc}")
    if not confirm:
        return ok(
            requires_confirm(
                "Run SQB benchmark",
                f"dataset={dataset}",
            )
        )
    try:
        await require_feature(identity, "gateway", "benchmark")
    except PermissionError as exc:
        return err(str(exc))

    client = GatewayClient()
    try:
        result = await client.run_benchmark(dataset)
        return ok({"live": True, **result})
    except (BackendNotConfigured, BackendError):
        return ok(
            {
                "live": False,
                "message": "Gateway backend unavailable; returning stub.",
                "dataset": dataset,
            }
        )
