# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Stripe billing integration for CRP hosted tools.

This module maps Stripe subscription price IDs to product features and creates
Stripe Checkout sessions for plan upgrades.  It is designed to degrade cleanly
when Stripe is not configured.
"""

from __future__ import annotations

import asyncio
import os
from typing import Any

from crp_mcp.types import err, ok

try:
    import stripe as stripe_lib
except Exception:  # pragma: no cover
    stripe_lib = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
def stripe_available() -> bool:
    return stripe_lib is not None and bool(os.environ.get("STRIPE_SECRET_KEY"))


def _stripe() -> Any:
    if stripe_lib is None:
        raise RuntimeError("stripe package is not installed")
    stripe_lib.api_key = os.environ.get("STRIPE_SECRET_KEY", "")
    return stripe_lib


# Map each product/plan combination to its Stripe price ID.
def _price_id(product: str, plan: str) -> str | None:
    env_map = {
        ("gateway", "developer"): "STRIPE_GATEWAY_DEVELOPER_PRICE_ID",
        ("gateway", "team"): "STRIPE_GATEWAY_TEAM_PRICE_ID",
        ("comply", "starter"): "STRIPE_COMPLY_STARTER_PRICE_ID",
        ("comply", "scale"): "STRIPE_COMPLY_SCALE_PRICE_ID",
        ("scan", "starter"): "STRIPE_SCAN_STARTER_PRICE_ID",
        ("scan", "scale"): "STRIPE_SCAN_SCALE_PRICE_ID",
    }
    return os.environ.get(env_map.get((product, plan), ""))


# Features granted by each price ID.  This mirrors the feature gating in the CRP
# billing service and avoids a network round-trip on every tool call.
_PRICE_FEATURES: dict[str, dict[str, Any]] = {
    "STRIPE_GATEWAY_DEVELOPER_PRICE_ID": {
        "plan": "developer",
        "features": ["view_plan", "create_api_key", "test_call"],
    },
    "STRIPE_GATEWAY_TEAM_PRICE_ID": {
        "plan": "team",
        "features": [
            "view_plan",
            "create_api_key",
            "test_call",
            "deploy_endpoint",
            "benchmark",
        ],
    },
    "STRIPE_COMPLY_STARTER_PRICE_ID": {
        "plan": "starter",
        "features": ["view_plan", "comply_repo", "comply_status", "comply_diff"],
    },
    "STRIPE_COMPLY_SCALE_PRICE_ID": {
        "plan": "scale",
        "features": [
            "view_plan",
            "comply_repo",
            "comply_status",
            "comply_diff",
            "comply_policy",
            "scan_repo",
            "scan_status",
            "scan_report",
        ],
    },
    "STRIPE_SCAN_STARTER_PRICE_ID": {
        "plan": "starter",
        "features": ["view_plan", "scan_repo", "scan_status", "scan_report"],
    },
    "STRIPE_SCAN_SCALE_PRICE_ID": {
        "plan": "scale",
        "features": [
            "view_plan",
            "scan_repo",
            "scan_status",
            "scan_report",
            "comply_repo",
        ],
    },
}


def _resolve_price_features(price_id: str) -> dict[str, Any] | None:
    for env_name, meta in _PRICE_FEATURES.items():
        if os.environ.get(env_name) == price_id:
            return meta
    return None


# ---------------------------------------------------------------------------
# Entitlements
# ---------------------------------------------------------------------------
def _empty_entitlement(product: str) -> dict[str, Any]:
    return {
        "product": product,
        "plan": "free",
        "features": ["view_plan"],
        "quota": {},
        "live": False,
    }


async def get_entitlement(identity: Any, product: str) -> dict[str, Any]:
    """Return the caller's entitlement for a CRP product.

    In hosted mode with Stripe configured this searches for an active Stripe
    subscription keyed by the caller's ``org_id``.  Otherwise it returns a safe
    free-tier stub that only grants read-only ``view_plan``.
    """
    if not stripe_available():
        return _empty_entitlement(product)

    org_id = getattr(identity, "org_id", None)
    if not org_id:
        return _empty_entitlement(product)

    try:
        # Stripe customer search is synchronous; run it in a thread so the async
        # MCP runtime is not blocked.
        loop = asyncio.get_running_loop()
        customer = await loop.run_in_executor(
            None,
            lambda: _stripe().Customer.search(
                query=f"metadata['crp_org_id']:'{org_id}'",
                limit=1,
            ),
        )
    except Exception:
        return _empty_entitlement(product)

    if not customer or not customer.data:
        return _empty_entitlement(product)

    customer_id = customer.data[0].id
    features = {"view_plan"}
    plan = "free"
    quota: dict[str, Any] = {}

    try:
        loop = asyncio.get_running_loop()
        subscriptions = await loop.run_in_executor(
            None,
            lambda: _stripe().Subscription.list(
                customer=customer_id,
                status="active",
                limit=100,
            ),
        )
    except Exception:
        subscriptions = None

    if subscriptions:
        for sub in subscriptions.auto_paging_iter():
            for item in sub.get("items", {}).get("data", []):
                price_id = item.get("price", {}).get("id")
                meta = _resolve_price_features(price_id)
                if meta:
                    features.update(meta.get("features", []))
                    plan = meta.get("plan", plan)
            # Quota metadata can be stored on the subscription itself.
            sub_meta = sub.get("metadata", {}) or {}
            for key, value in sub_meta.items():
                if key.startswith("quota_"):
                    quota[key[6:]] = value

    return {
        "product": product,
        "plan": plan,
        "features": sorted(features),
        "quota": quota,
        "live": True,
    }


# ---------------------------------------------------------------------------
# Checkout sessions
# ---------------------------------------------------------------------------
def _base_origin() -> str:
    return os.environ.get("CRP_PUBLIC_ORIGIN", "https://crprotocol.io").rstrip("/")


def _checkout_url_fallback(product: str, plan: str) -> str:
    return f"https://crprotocol.io/upgrade/{product}/{plan}"


async def create_checkout_session(
    identity: Any,
    product: str,
    plan: str,
) -> dict[str, Any]:
    """Create a Stripe Checkout session and return its URL.

    Falls back to the static upgrade URL if Stripe is not configured.
    """
    if not stripe_available():
        return {
            "ok": True,
            "configured": False,
            "action": "open_in_browser",
            "url": _checkout_url_fallback(product, plan),
            "message": "Stripe is not configured. Open the static upgrade page.",
        }

    price_id = _price_id(product, plan)
    if not price_id:
        return {
            "ok": False,
            "error": f"No Stripe price configured for {product}/{plan}.",
        }

    org_id = getattr(identity, "org_id", None)
    user_id = getattr(identity, "user_id", None) or "anonymous"
    origin = _base_origin()

    params: dict[str, Any] = {
        "mode": "subscription",
        "line_items": [{"price": price_id, "quantity": 1}],
        "success_url": f"{origin}/upgrade/success?session_id={{CHECKOUT_SESSION_ID}}",
        "cancel_url": f"{origin}/upgrade/cancel",
        "client_reference_id": org_id or user_id,
        "allow_promotion_codes": True,
        "subscription_data": {
            "metadata": {"crp_org_id": org_id or user_id, "crp_user_id": user_id},
        },
    }

    try:
        session = await asyncio.to_thread(_stripe().checkout.Session.create, **params)
    except Exception as exc:
        return {
            "ok": False,
            "configured": True,
            "error": f"stripe_checkout_failed: {exc}",
        }

    return {
        "ok": True,
        "configured": True,
        "action": "open_in_browser",
        "url": session.url,
        "session_id": session.id,
        "message": "Complete payment in your browser to activate the plan.",
    }


def format_upgrade_result(result: dict[str, Any]) -> str:
    if result.get("ok"):
        return ok(result)
    return err(result.get("error", "upgrade_failed"))
