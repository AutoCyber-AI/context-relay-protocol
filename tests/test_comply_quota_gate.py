# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Tests for CRP Comply Quota Gate."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from crp.comply.billing.metering import period_key
from crp.comply.quota_gate import QuotaGate


class TestQuotaGate:
    @patch("crp.comply.quota_gate.get_org_entitlement")
    def test_within_quota_returns_ok(self, mock_ent: MagicMock) -> None:
        mock_ent.return_value = {"plan": "free", "quota": 100, "credit_balance_cents": 0}
        gate = QuotaGate()
        result = gate.check("org_a")
        assert result["status"] == "ok"
        assert result["quota"] == 100

    @patch("crp.comply.quota_gate.get_org_entitlement")
    def test_over_quota_with_credits_returns_ok_credit(self, mock_ent: MagicMock) -> None:
        mock_ent.return_value = {"plan": "free", "quota": 1, "credit_balance_cents": 50}
        gate = QuotaGate()
        gate._store.increment("org_a", period_key())
        gate._store.increment("org_a", period_key())
        result = gate.check("org_a")
        assert result["status"] == "ok_credit"
        assert result["credits_remaining_cents"] == 50

    @patch("crp.comply.quota_gate.get_org_entitlement")
    def test_over_quota_without_credits_returns_exceeded(self, mock_ent: MagicMock) -> None:
        mock_ent.return_value = {"plan": "free", "quota": 1, "credit_balance_cents": 0}
        gate = QuotaGate()
        gate._store.increment("org_a", period_key())
        gate._store.increment("org_a", period_key())
        result = gate.check("org_a")
        assert result["status"] == "quota_exceeded"
        assert result["action"] == "prompt_topup_or_upgrade"

    @patch("crp.comply.quota_gate.get_org_entitlement")
    def test_fail_open_on_entitlement_error(self, mock_ent: MagicMock) -> None:
        mock_ent.side_effect = RuntimeError("clerk down")
        gate = QuotaGate()
        result = gate.check("org_b")
        assert result["status"] == "ok"
        assert result["note"] == "entitlement_unavailable"

    def test_record_usage(self) -> None:
        gate = QuotaGate()
        r1 = gate.record_usage("org_c")
        assert r1["used"] == 1
        r2 = gate.record_usage("org_c")
        assert r2["used"] == 2
