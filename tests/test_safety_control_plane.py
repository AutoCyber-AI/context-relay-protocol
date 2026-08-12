# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Tests for Safety Control Plane, Checkpoint, Coverage, and Manifest (SPEC-033, SPEC-034)."""

from __future__ import annotations

import pytest

from crp.security.checkpoint import (
    Checkpoint,
    CheckpointRejectAction,
    CheckpointResolution,
    CheckpointResolutionAction,
    CheckpointTimeoutAction,
    CheckpointTrigger,
)
from crp.security.control_plane import SafetyControlPlane, get_default_control_plane
from crp.security.coverage import SafetyCapability, SafetyCoverageMap
from crp.security.safety_manifest import SafetyManifest


class TestSafetyManifest:
    def test_default_profile(self) -> None:
        m = SafetyManifest()
        assert m.profile == "balanced"
        assert m.get("hallucination_halt") == "CRITICAL"

    def test_strict_profile(self) -> None:
        m = SafetyManifest(profile="strict")
        assert m.get("hallucination_halt") == "HIGH"
        assert m.get("pii_handling") == "block"

    def test_hash_deterministic(self) -> None:
        m1 = SafetyManifest(profile="balanced")
        m2 = SafetyManifest(profile="balanced")
        assert m1.compute_hash() == m2.compute_hash()

    def test_hash_changes_on_tune(self) -> None:
        m = SafetyManifest(profile="balanced")
        h1 = m.compute_hash()
        m.set("require_grounding", 0.99)
        h2 = m.compute_hash()
        assert h1 != h2

    def test_roundtrip_dict(self) -> None:
        m = SafetyManifest(profile="medical")
        d = m.to_dict()
        m2 = SafetyManifest.from_dict(d)
        assert m2.profile == "medical"


class TestSafetyCoverageMap:
    def test_default_out_of_scope(self) -> None:
        cm = SafetyCoverageMap()
        assert "model_alignment" in cm.out_of_scope
        assert "training_data_bias" in cm.out_of_scope

    def test_register_and_get(self) -> None:
        cm = SafetyCoverageMap()
        cap = SafetyCapability(
            name="test_cap",
            description="test",
            spec="999",
            default="on",
            current="on",
            addable=True,
        )
        cm.register(cap)
        assert cm.get("test_cap") is not None
        assert len(cm.list_addable()) == 1


class TestCheckpoint:
    def test_auto_id(self) -> None:
        cp = Checkpoint()
        assert cp.checkpoint_id
        assert cp.trigger == CheckpointTrigger.ALWAYS

    def test_timeout_defaults(self) -> None:
        cp = Checkpoint()
        assert cp.timeout == 300
        assert cp.on_timeout == CheckpointTimeoutAction.ESCALATE
        assert cp.on_reject == CheckpointRejectAction.FALLBACK

    @pytest.mark.asyncio
    async def test_wait_for_resolution_timeout(self) -> None:
        cp = Checkpoint(timeout=0)
        resolution = await cp.wait_for_resolution()
        assert resolution.action == CheckpointResolutionAction.REJECT
        assert resolution.reviewer == "system/auto-timeout"

    def test_resolve(self) -> None:
        cp = Checkpoint()
        res = CheckpointResolution(
            action=CheckpointResolutionAction.APPROVE,
            reviewer="test",
        )
        cp.resolve(res)
        assert cp._resolution is not None


class TestSafetyControlPlane:
    def test_built_in_capabilities(self) -> None:
        scp = SafetyControlPlane()
        assert scp.get_capability("hallucination_risk_scoring") is not None
        assert scp.get_capability("http_451_halt") is not None
        assert len(scp.list_capabilities()) >= 13

    def test_tune(self) -> None:
        scp = SafetyControlPlane()
        scp.tune("grounding_verification", 0.85)
        cap = scp.get_capability("grounding_verification")
        assert cap is not None
        assert cap.current == 0.85
        assert scp.manifest.get("grounding_verification") == 0.85

    def test_surface_map(self) -> None:
        scp = SafetyControlPlane()
        surface = scp.get_surface_map()
        assert "registry" in surface
        assert "manifest" in surface
        assert "coverage" in surface

    def test_show_output(self) -> None:
        scp = SafetyControlPlane()
        text = scp.show()
        assert "CRP SAFETY CONTROL PLANE" in text
        assert "OUT OF SCOPE" in text

    def test_singleton(self) -> None:
        scp1 = get_default_control_plane()
        scp2 = get_default_control_plane()
        assert scp1 is scp2

    def test_create_checkpoint(self) -> None:
        scp = SafetyControlPlane()
        cp = scp.create_checkpoint(trigger="always", timeout=60)
        assert cp.checkpoint_id in scp._checkpoints
