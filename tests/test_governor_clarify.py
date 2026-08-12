# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Tests for the Resource Governor (slow-and-steady) and the CLARIFY bridge (CRP v5)."""

from __future__ import annotations

from typing import Any

from crp.resources import DeviceProfile, DeviceTier, ResourceGovernor, ResourcePlan
from crp.security import (
    ClarificationAction,
    ClarificationRequest,
    ClarificationResolution,
    resolve_clarification,
)
from crp.stl import run_positioned
from crp.tools import (
    CapabilityExecutor,
    CapabilityProfile,
    SafetyClass,
    ToolCapabilityFabric,
)


def _cap(cid: str, op: str, *, safety: str = "read-only", desc: str = "") -> dict[str, Any]:
    return {
        "capability_id": cid, "kind": "tool", "version": "1.0.0",
        "operation_types": [op],
        "input_schema": {"type": "object", "properties": {}, "required": []},
        "output_schema": {"type": "object"}, "produces_facts": True,
        "cost_profile": {"tokens": 50, "latency_ms": 100, "safety_class": safety},
        "metadata": {"description": desc},
    }


def _tool_model(tool_json: str, text: str = "direct output"):
    def _call(prompt: str, schema: dict[str, Any] | None) -> str:
        return tool_json if schema is not None else text
    return _call


# ── Resource Governor ───────────────────────────────────────────────────────


class TestResourceGovernor:
    def test_detect_device_returns_profile(self) -> None:
        dev = ResourceGovernor.detect_device()
        assert isinstance(dev, DeviceProfile)
        assert dev.cpu_count >= 1

    def test_constrained_plan(self) -> None:
        gov = ResourceGovernor(device=DeviceProfile(DeviceTier.CONSTRAINED, 2, 4.0))
        plan = gov.plan()
        assert isinstance(plan, ResourcePlan)
        assert plan.profile is CapabilityProfile.SMALL_LOCAL
        assert plan.max_operations == 6
        assert plan.tool_concurrency == 1
        assert "slow-and-steady" in plan.reason

    def test_caps_requested_profile_down(self) -> None:
        gov = ResourceGovernor(device=DeviceProfile(DeviceTier.CONSTRAINED, 2, 4.0))
        plan = gov.plan(CapabilityProfile.FRONTIER)
        assert plan.profile is CapabilityProfile.SMALL_LOCAL  # never upsizes beyond tier
        assert "capped from frontier" in plan.reason

    def test_honours_smaller_request_on_generous(self) -> None:
        gov = ResourceGovernor(device=DeviceProfile(DeviceTier.GENEROUS, 16, 64.0))
        assert gov.plan().profile is CapabilityProfile.FRONTIER  # ceiling
        assert gov.plan(CapabilityProfile.SMALL_LOCAL).profile is CapabilityProfile.SMALL_LOCAL

    def test_unknown_ram_is_constrained(self) -> None:
        from crp.resources.governor import _classify  # noqa: PLC0415
        assert _classify(8, 0.0) is DeviceTier.CONSTRAINED  # unknown RAM → safe default
        assert _classify(2, 4.0) is DeviceTier.CONSTRAINED
        assert _classify(16, 64.0) is DeviceTier.GENEROUS

    def test_governor_in_positioned_loop(self) -> None:
        gov = ResourceGovernor(device=DeviceProfile(DeviceTier.CONSTRAINED, 2, 4.0))
        res = run_positioned("write a short note", _tool_model("", text="note"), governor=gov)
        assert res.headers["CRP-Agent-Capability-Profile"] == "small-local"
        assert "CRP-Resource-Plan" in res.headers


# ── Clarification bridge ────────────────────────────────────────────────────


class TestClarification:
    def test_no_handler_falls_back_to_skip(self) -> None:
        req = ClarificationRequest(question="?")
        res = resolve_clarification(req, None)
        assert res.action is ClarificationAction.SKIP

    def test_handler_exception_falls_back(self) -> None:
        def boom(_req: ClarificationRequest) -> ClarificationResolution:
            raise RuntimeError("handler down")
        res = resolve_clarification(ClarificationRequest(question="?"), boom)
        assert res.action is ClarificationAction.SKIP

    def test_handler_answer_passes_through(self) -> None:
        def handler(_req: ClarificationRequest) -> ClarificationResolution:
            return ClarificationResolution(ClarificationAction.ANSWER, answer="42")
        res = resolve_clarification(ClarificationRequest(question="?"), handler)
        assert res.action is ClarificationAction.ANSWER and res.answer == "42"

    def test_bad_return_falls_back(self) -> None:
        res = resolve_clarification(ClarificationRequest(question="?"), lambda r: "nope")  # type: ignore[arg-type,return-value]
        assert res.action is ClarificationAction.SKIP

    def test_approved_property(self) -> None:
        assert ClarificationResolution(ClarificationAction.ANSWER, answer="approve").approved
        assert not ClarificationResolution(ClarificationAction.SKIP).approved


# ── CLARIFY + oversight in the positioned loop ──────────────────────────────


class TestClarifyInLoop:
    def test_clarify_operation_prompts_user(self) -> None:
        def handler(_req: ClarificationRequest) -> ClarificationResolution:
            return ClarificationResolution(ClarificationAction.ANSWER, answer="I meant the EU AI Act")
        res = run_positioned(
            "can you clarify what you meant",
            _tool_model("", text="(model guess)"),
            clarify_handler=handler,
        )
        assert "EU AI Act" in res.text
        assert any("User clarification" in f.statement for f in res.cso.established_facts)

    def test_clarify_without_handler_best_effort(self) -> None:
        res = run_positioned("can you clarify what you meant", _tool_model("", text="best effort"))
        assert not res.halted
        assert res.state_machine is not None and res.state_machine.is_complete

    def test_oversight_approved_executes(self) -> None:
        tcf = ToolCapabilityFabric()
        tcf.register_dict(_cap("delete_db", "TRANSFORM", safety="destructive", desc="delete the database"))
        ex = CapabilityExecutor()
        ex.register_impl("delete_db", lambda args: "deleted")

        def approve(_req: ClarificationRequest) -> ClarificationResolution:
            return ClarificationResolution(ClarificationAction.ANSWER, answer="approve")

        res = run_positioned(
            "convert and wipe the data",
            _tool_model('{"capability_id": "delete_db", "arguments": {}}'),
            fabric=tcf, executor=ex,
            oversight_required={SafetyClass.DESTRUCTIVE},
            clarify_handler=approve,
        )
        assert not res.halted
        assert res.observation_count == 1

    def test_oversight_denied_halts(self) -> None:
        tcf = ToolCapabilityFabric()
        tcf.register_dict(_cap("delete_db", "TRANSFORM", safety="destructive", desc="delete the database"))
        ex = CapabilityExecutor()
        ex.register_impl("delete_db", lambda args: "deleted")

        def deny(_req: ClarificationRequest) -> ClarificationResolution:
            return ClarificationResolution(ClarificationAction.SKIP)

        res = run_positioned(
            "convert and wipe the data",
            _tool_model('{"capability_id": "delete_db", "arguments": {}}'),
            fabric=tcf, executor=ex,
            oversight_required={SafetyClass.DESTRUCTIVE},
            clarify_handler=deny,
        )
        assert res.halted
        assert len(res.cso.preventive_halt_history) == 1
