# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Live Stripe price IDs and entitlement maps for CRP Comply (SPEC-047 §1).

All price IDs are LIVE on AutoCyber AI (acct_1TLbVkGRBK524I7z).
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Price IDs — single source of truth
# ---------------------------------------------------------------------------

PRICE_TO_PLAN: dict[str, str] = {
    # CRP Comply
    "price_1Te0k1GRBK524I7zrLssfPVt": "comply_starter",   # Starter monthly
    "price_1Te0k5GRBK524I7zgWdvIRLy": "comply_starter",   # Starter annual
    "price_1Te0kDGRBK524I7z8zwCrNUD": "comply_scale",     # Scale monthly
    "price_1Te0kGGRBK524I7zQcnbPrPY": "comply_scale",     # Scale annual
    "price_1Te0kOGRBK524I7z8OmtD5Lp": "comply_credits",   # Credits $5
    "price_1Te0kRGRBK524I7zMOvbrXW5": "comply_credits",   # Credits $20
    "price_1Te0kUGRBK524I7zTccpMVZc": "comply_credits",   # Credits $50
    # CRP Scan
    "price_1Te0kfGRBK524I7zrMHu3BXL": "scan_pro",         # Pro per repo
    "price_1Te0kmGRBK524I7zBKcUu6h6": "scan_business",    # Business
    # CRP Gateway
    "price_1Te0kvGRBK524I7zbhruWdHb": "gateway_developer", # Developer monthly
    "price_1Te0kzGRBK524I7zZMQ4r1G7": "gateway_developer", # Developer annual
    "price_1Te0l6GRBK524I7zk7qU16TX": "gateway_team",     # Team monthly
    "price_1Te0lAGRBK524I7zac5aYFPK": "gateway_team",     # Team annual
}

PRODUCTS: dict[str, str] = {
    "comply_starter": "prod_UdHIRpesJB0WFu",
    "comply_scale": "prod_UdHIYA1Wd8li76",
    "comply_credits": "prod_UdHI25gm6SNnIp",
    "scan_pro": "prod_UdHJBTmWYH1f99",
    "scan_business": "prod_UdHJyQYThV1Qgg",
    "gateway_developer": "prod_UdHJhh55IaExpq",
    "gateway_team": "prod_UdHJVfhfLrueep",
}

# ---------------------------------------------------------------------------
# Quotas — audited calls per month
# ---------------------------------------------------------------------------

PLAN_QUOTAS: dict[str, int] = {
    "free": 100,
    "comply_starter": 5_000,
    "comply_scale": 50_000,
    "gateway_developer": 50_000,
    "gateway_team": 500_000,
    "scan_pro": 0,       # scan_pro is per-repo, not call-quota
    "scan_business": 0,  # scan_business is unlimited repos
}

# ---------------------------------------------------------------------------
# Features per plan
# ---------------------------------------------------------------------------

PLAN_FEATURES: dict[str, list[str]] = {
    "free": ["governance"],
    "comply_starter": [
        "governance",
        "checkpoint_inbox",
        "evidence_pack",
        "hosted_vault",
        "scan_remediations",
    ],
    "comply_scale": [
        "governance",
        "checkpoint_inbox",
        "evidence_pack",
        "hosted_vault",
        "scan_remediations",
        "sso",
        "data_residency",
        "custom_rules",
        "hosted_llm",
    ],
    "gateway_developer": [
        "governance",
        "context_suite",
        "console",
        "deploy_endpoint",
    ],
    "gateway_team": [
        "governance",
        "context_suite",
        "console",
        "deploy_endpoint",
        "shared_pipelines",
        "sso",
    ],
    "scan_pro": ["scan_remediation_pr"],
    "scan_business": [
        "scan_remediation_pr",
        "unlimited_repos",
        "campaigns",
    ],
}

# ---------------------------------------------------------------------------
# Credit top-ups — cents added per price ID
# ---------------------------------------------------------------------------

CREDIT_CENTS_FROM_PRICE: dict[str, int] = {
    "price_1Te0kOGRBK524I7z8OmtD5Lp": 500,    # $5
    "price_1Te0kRGRBK524I7zMOvbrXW5": 2_000,  # $20
    "price_1Te0kUGRBK524I7zTccpMVZc": 5_000,  # $50
}

# Metering event name for Stripe Meter Events API
METER_EVENT_NAME: str = "comply_proxy_requests"

# Credit cost per audited call (in cents) — drawn after quota exceeded
CREDIT_COST_PER_CALL_CENTS: int = 1  # 1 cent per 100 calls over quota
