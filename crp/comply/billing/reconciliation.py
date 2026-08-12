# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Nightly reconciliation — compare Stripe subscriptions to Clerk entitlement.

Repairs drift from missed webhooks (SPEC-047 §3.2).
"""

from __future__ import annotations

import logging
from typing import Any

import requests
import stripe

from crp.comply.billing.constants import PLAN_FEATURES, PLAN_QUOTAS
from crp.comply.billing.entitlements import plan_from_price_id
from crp.comply.billing.webhook import _clerk_headers, _update_clerk_org

logger = logging.getLogger(__name__)


def reconcile_subscriptions(
    dry_run: bool = False,
    limit: int = 100,
) -> dict[str, Any]:
    """Walk active Stripe subscriptions and ensure Clerk org metadata matches.

    Args:
        dry_run: If True, log differences but do not write to Clerk.
        limit: Max subscriptions to check.

    Returns:
        Dict with ``checked``, ``repaired``, ``errors`` counts.
    """
    result = {"checked": 0, "repaired": 0, "errors": 0, "details": []}

    try:
        subs = stripe.Subscription.list(
            status="active",
            limit=limit,
            expand=["data.customer"],
        )
    except Exception as exc:
        logger.error("Failed to list Stripe subscriptions: %s", exc)
        result["errors"] += 1
        return result

    for sub in subs.auto_paging_iter():
        if result["checked"] >= limit:
            break
        result["checked"] += 1

        customer = sub.get("customer")
        if not customer:
            continue

        org_id = None
        if isinstance(customer, dict) and customer.get("metadata"):
            org_id = customer["metadata"].get("clerkOrgId")

        if not org_id:
            logger.debug("Skipping sub %s — no clerkOrgId linkage", sub["id"])
            continue

        # Determine expected plan from subscription
        try:
            price_id = sub["items"]["data"][0]["price"]["id"]
            expected_plan = plan_from_price_id(price_id)
        except (IndexError, KeyError):
            logger.warning("Sub %s has no price item", sub["id"])
            continue

        # Read current Clerk entitlement
        try:
            org_url = f"https://api.clerk.com/v1/organizations/{org_id}"
            r = requests.get(org_url, headers=_clerk_headers(), timeout=5.0)
            r.raise_for_status()
            current_meta = r.json().get("public_metadata", {})
            current_plan = current_meta.get("plan", "free")
        except Exception as exc:
            logger.warning("Cannot read Clerk org %s: %s", org_id, exc)
            result["errors"] += 1
            continue

        if current_plan != expected_plan:
            detail = {
                "org_id": org_id,
                "sub_id": sub["id"],
                "current_plan": current_plan,
                "expected_plan": expected_plan,
            }
            result["details"].append(detail)
            logger.info("Drift detected: %s", detail)

            if not dry_run:
                try:
                    _update_clerk_org(
                        org_id,
                        {
                            "plan": expected_plan,
                            "stripeSubscriptionId": sub["id"],
                            "quota": PLAN_QUOTAS.get(expected_plan, 100),
                            "features": PLAN_FEATURES.get(expected_plan, ["governance"]),
                            "currentPeriodEnd": sub.get("current_period_end"),
                        },
                    )
                    result["repaired"] += 1
                except Exception as exc:
                    logger.error("Failed to repair org %s: %s", org_id, exc)
                    result["errors"] += 1

    logger.info(
        "Reconciliation complete: checked=%d repaired=%d errors=%d",
        result["checked"], result["repaired"], result["errors"],
    )
    return result
