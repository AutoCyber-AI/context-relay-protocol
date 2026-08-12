# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Tests for CRP Comply billing module (SPEC-047).

All external APIs (Stripe, Clerk) are mocked — no live network calls.
"""

from __future__ import annotations

import json
import os
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from crp.comply.billing.constants import (
    CREDIT_CENTS_FROM_PRICE,
    PLAN_FEATURES,
    PLAN_QUOTAS,
    PRICE_TO_PLAN,
)
from crp.comply.billing.entitlements import (
    features_for,
    get_org_entitlement,
    plan_from_price_id,
    quota_for,
    require_feature,
)
from crp.comply.billing.metering import InMemoryUsageStore, Metering, period_key
from crp.comply.billing.webhook import StripeWebhookHandler

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_xxx")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test_xxx")
    monkeypatch.setenv("CLERK_SECRET_KEY", "sk_test_clerk_xxx")
    # Reset module-level caches so each test starts fresh
    import crp.comply.billing.entitlements as _ent
    _ent._CLERK_SECRET = None
    import crp.comply.billing.webhook as _wh
    _wh._STRIPE_WEBHOOK_SECRET = None


# ---------------------------------------------------------------------------
# Constants / entitlement mapping
# ---------------------------------------------------------------------------


class TestPlanMapping:
    def test_plan_from_price_id_comply_starter_monthly(self) -> None:
        assert plan_from_price_id("price_1Te0k1GRBK524I7zrLssfPVt") == "comply_starter"

    def test_plan_from_price_id_comply_scale_annual(self) -> None:
        assert plan_from_price_id("price_1Te0kGGRBK524I7zQcnbPrPY") == "comply_scale"

    def test_plan_from_price_id_unknown_returns_free(self) -> None:
        assert plan_from_price_id("price_unknown") == "free"

    def test_quota_for_free(self) -> None:
        assert quota_for("free") == 100

    def test_quota_for_scale(self) -> None:
        assert quota_for("comply_scale") == 50_000

    def test_features_for_starter(self) -> None:
        feats = features_for("comply_starter")
        assert "governance" in feats
        assert "checkpoint_inbox" in feats

    def test_features_for_unknown_defaults_to_governance(self) -> None:
        assert features_for("nonexistent") == ["governance"]


# ---------------------------------------------------------------------------
# Clerk entitlement read
# ---------------------------------------------------------------------------


class TestGetOrgEntitlement:
    @patch("crp.comply.billing.entitlements.requests.get")
    def test_reads_plan_and_quota(self, mock_get: MagicMock) -> None:
        mock_get.return_value.json.return_value = {
            "public_metadata": {
                "plan": "comply_starter",
                "quota": 5_000,
                "features": ["governance"],
                "creditBalanceCents": 100,
                "stripeCustomerId": "cus_123",
            }
        }
        mock_get.return_value.raise_for_status = lambda: None

        ent = get_org_entitlement("org_test_123")
        assert ent["plan"] == "comply_starter"
        assert ent["quota"] == 5_000
        assert ent["credit_balance_cents"] == 100
        assert ent["stripe_customer_id"] == "cus_123"

    @patch("crp.comply.billing.entitlements.requests.get")
    def test_defaults_when_metadata_empty(self, mock_get: MagicMock) -> None:
        mock_get.return_value.json.return_value = {"public_metadata": {}}
        mock_get.return_value.raise_for_status = lambda: None

        ent = get_org_entitlement("org_empty")
        assert ent["plan"] == "free"
        assert ent["quota"] == 100

    def test_raises_without_clerk_secret(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("CLERK_SECRET_KEY", raising=False)
        # Reset the module-level cache so the missing env is detected
        import crp.comply.billing.entitlements as _ent
        _ent._CLERK_SECRET = None
        with pytest.raises(RuntimeError, match="CLERK_SECRET_KEY"):
            get_org_entitlement("org_x")
        # Restore for subsequent tests (fixture will also reset, but be safe)
        _ent._CLERK_SECRET = None


class TestRequireFeature:
    @patch("crp.comply.billing.entitlements.requests.get")
    def test_allows_when_feature_present(self, mock_get: MagicMock) -> None:
        mock_get.return_value.json.return_value = {
            "public_metadata": {
                "plan": "comply_scale",
                "features": PLAN_FEATURES["comply_scale"],
            }
        }
        mock_get.return_value.raise_for_status = lambda: None

        ent = require_feature("org_scale", "sso")
        assert ent["plan"] == "comply_scale"

    @patch("crp.comply.billing.entitlements.requests.get")
    def test_rejects_when_feature_missing(self, mock_get: MagicMock) -> None:
        mock_get.return_value.json.return_value = {
            "public_metadata": {
                "plan": "comply_starter",
                "features": PLAN_FEATURES["comply_starter"],
            }
        }
        mock_get.return_value.raise_for_status = lambda: None

        with pytest.raises(PermissionError, match="upgrade_required:sso"):
            require_feature("org_starter", "sso")


# ---------------------------------------------------------------------------
# Stripe webhook handler
# ---------------------------------------------------------------------------


class TestStripeWebhookHandler:
    @patch("stripe.Webhook.construct_event")
    def test_verifies_signature(self, mock_construct: MagicMock) -> None:
        from stripe._error import SignatureVerificationError
        mock_construct.side_effect = SignatureVerificationError("bad sig", "hdr")
        handler = StripeWebhookHandler(webhook_secret="whsec_test")
        result = handler.process(b"payload", "bad_sig")
        assert result["status"] == 400
        assert "signature" in result["error"].lower()

    @patch("stripe.Webhook.construct_event")
    def test_idempotent_dedupe(self, mock_construct: MagicMock) -> None:
        event = {
            "id": "evt_dup_123",
            "type": "checkout.session.completed",
            "data": {"object": {"metadata": {"clerkOrgId": "org_1"}}},
        }
        mock_construct.return_value = event
        handler = StripeWebhookHandler(webhook_secret="whsec_test")

        r1 = handler.process(b"payload", "sig")
        assert r1["received"] is True
        assert r1.get("deduplicated") is not True

        r2 = handler.process(b"payload", "sig")
        assert r2["received"] is True
        assert r2.get("deduplicated") is True

    @patch("crp.comply.billing.webhook._update_clerk_org")
    @patch("stripe.Subscription.retrieve")
    @patch("stripe.Webhook.construct_event")
    def test_checkout_subscription_grants_plan(
        self,
        mock_construct: MagicMock,
        mock_sub: MagicMock,
        mock_update: MagicMock,
    ) -> None:
        mock_sub.return_value = {
            "id": "sub_123",
            "items": {"data": [{"price": {"id": "price_1Te0k1GRBK524I7zrLssfPVt"}}]},
            "current_period_end": 1_800_000_000,
        }
        event = {
            "id": "evt_sub_001",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "mode": "subscription",
                    "subscription": "sub_123",
                    "metadata": {"clerkOrgId": "org_grant"},
                }
            },
        }
        mock_construct.return_value = event
        handler = StripeWebhookHandler(webhook_secret="whsec_test")
        result = handler.process(b"payload", "sig")
        assert result["received"] is True
        mock_update.assert_called_once()
        args = mock_update.call_args
        assert args[0][0] == "org_grant"
        meta = args[0][1]
        assert meta["plan"] == "comply_starter"
        assert meta["stripeSubscriptionId"] == "sub_123"

    @patch("crp.comply.billing.webhook._update_clerk_org")
    @patch("stripe.Webhook.construct_event")
    def test_subscription_deleted_downgrades_to_free(
        self,
        mock_construct: MagicMock,
        mock_update: MagicMock,
    ) -> None:
        with patch("crp.comply.billing.webhook._org_id_from_customer", return_value="org_down"):
            event = {
                "id": "evt_del_001",
                "type": "customer.subscription.deleted",
                "data": {"object": {"customer": "cus_down"}},
            }
            mock_construct.return_value = event
            handler = StripeWebhookHandler(webhook_secret="whsec_test")
            result = handler.process(b"payload", "sig")
            assert result["received"] is True
            mock_update.assert_called_once()
            meta = mock_update.call_args[0][1]
            assert meta["plan"] == "free"
            assert meta["quota"] == 100


# ---------------------------------------------------------------------------
# Metering / quota
# ---------------------------------------------------------------------------


class TestInMemoryUsageStore:
    def test_increment_and_get(self) -> None:
        store = InMemoryUsageStore()
        assert store.increment("org_a", "2026-06") == 1
        assert store.increment("org_a", "2026-06") == 2
        assert store.get("org_a", "2026-06") == 2

    def test_credit_draw(self) -> None:
        store = InMemoryUsageStore()
        store.add_credit("org_a", 100)
        assert store.draw_credit("org_a", 30) is True
        assert store.draw_credit("org_a", 80) is False


class TestMetering:
    @patch("crp.comply.billing.metering.get_org_entitlement")
    def test_within_quota_returns_ok(self, mock_ent: MagicMock) -> None:
        mock_ent.return_value = {"plan": "free", "quota": 100, "credit_balance_cents": 0}
        m = Metering()
        result = m.record_call("org_free")
        assert result["status"] == "ok"
        assert result["used"] == 1

    @patch("crp.comply.billing.metering.get_org_entitlement")
    def test_exceeds_quota_without_credits(self, mock_ent: MagicMock) -> None:
        mock_ent.return_value = {"plan": "free", "quota": 1, "credit_balance_cents": 0}
        m = Metering()
        m.record_call("org_x")  # used=1, ok
        result = m.record_call("org_x")  # used=2, exceeded
        assert result["status"] == "quota_exceeded"

    @patch("crp.comply.billing.metering.get_org_entitlement")
    def test_exceeds_quota_with_credits_returns_ok_credit(self, mock_ent: MagicMock) -> None:
        mock_ent.return_value = {"plan": "free", "quota": 1, "credit_balance_cents": 100}
        m = Metering()
        m.record_call("org_x")
        result = m.record_call("org_x")
        assert result["status"] == "ok_credit"

    def test_period_key_format(self) -> None:
        pk = period_key()
        assert len(pk) == 7  # YYYY-MM
        assert pk.count("-") == 1


# ---------------------------------------------------------------------------
# Reconciliation
# ---------------------------------------------------------------------------


class TestReconciliation:
    @patch("crp.comply.billing.reconciliation.stripe.Subscription.list")
    @patch("crp.comply.billing.reconciliation.requests.get")
    def test_dry_run_detects_drift(self, mock_get: MagicMock, mock_list: MagicMock) -> None:
        mock_list.return_value.auto_paging_iter.return_value = [
            {
                "id": "sub_1",
                "customer": {
                    "id": "cus_1",
                    "metadata": {"clerkOrgId": "org_drift"},
                },
                "items": {"data": [{"price": {"id": "price_1Te0kDGRBK524I7z8zwCrNUD"}}]},
                "current_period_end": 1_800_000_000,
            }
        ]
        mock_get.return_value.json.return_value = {
            "public_metadata": {"plan": "comply_starter"}  # should be scale
        }
        mock_get.return_value.raise_for_status = lambda: None

        from crp.comply.billing.reconciliation import reconcile_subscriptions

        result = reconcile_subscriptions(dry_run=True, limit=10)
        assert result["checked"] == 1
        assert len(result["details"]) == 1
        assert result["details"][0]["expected_plan"] == "comply_scale"
        assert result["repaired"] == 0  # dry_run
