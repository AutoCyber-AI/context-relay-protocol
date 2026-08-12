# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Tests for Comply Gateway Client (SPEC-042)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from crp.comply.gateway_client import (
    get_evidence_pack,
    get_org_safety_surface,
    map_to_regulation,
    stream_audit_events,
)


class TestMapToRegulation:
    def test_safety_halt_maps_to_art_9_and_15(self) -> None:
        articles = map_to_regulation("safety_halt")
        assert "Art. 9 (Risk management)" in articles
        assert "Art. 15 (Robustness)" in articles

    def test_checkpoint_maps_to_art_14(self) -> None:
        articles = map_to_regulation("checkpoint_created")
        assert "Art. 14 (Human oversight)" in articles

    def test_unknown_event_defaults_to_logging(self) -> None:
        articles = map_to_regulation("unknown_event")
        assert "Art. 12 (Logging)" in articles


class TestStreamAuditEvents:
    def test_stream_and_retrieve(self) -> None:
        events = [
            {"event_type": "safety_halt", "risk_level": "CRITICAL"},
            {"event_type": "window_complete", "risk_level": "LOW"},
        ]
        stream_audit_events(events, "tenant_1")
        pack = get_evidence_pack("tenant_1")
        assert pack["event_count"] == 2
        assert pack["risk_summary"]["CRITICAL"] == 1
        assert "Art. 9 (Risk management)" in pack["article_coverage"]

    def test_period_filter(self) -> None:
        events = [{"event_type": "window_complete", "period": "2026-05"}]
        stream_audit_events(events, "tenant_2")
        pack = get_evidence_pack("tenant_2", period="2026-05")
        assert pack["event_count"] == 1
        pack_all = get_evidence_pack("tenant_2", period="2026-06")
        assert pack_all["event_count"] == 0


class TestGetOrgSafetySurface:
    @patch("crp.comply.gateway_client.get_org_entitlement")
    def test_gates_advanced_features_on_free_plan(self, mock_ent: MagicMock) -> None:
        mock_ent.return_value = {"plan": "free", "features": ["governance"]}
        surface = get_org_safety_surface("org_free")
        assert surface["org_plan"] == "free"
        # SSO should be gated out on free
        assert "sso" not in surface["registry"]

    @patch("crp.comply.gateway_client.get_org_entitlement")
    def test_allows_advanced_on_scale_plan(self, mock_ent: MagicMock) -> None:
        mock_ent.return_value = {"plan": "comply_scale", "features": ["governance", "sso"]}
        surface = get_org_safety_surface("org_scale")
        assert surface["org_plan"] == "comply_scale"
