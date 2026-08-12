# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Tests for the Tool Capability Fabric — positioning, not injection (CRP-SPEC-050)."""

from __future__ import annotations

from typing import Any

import pytest

from crp.stl.classifier import STLOperation
from crp.tools import (
    CapabilityDescriptor,
    CapabilityExecutor,
    CapabilityProfile,
    ExecutionStatus,
    PolicyContext,
    SafetyClass,
    ToolCapabilityFabric,
    max_capabilities,
    validate_arguments,
)


def _desc(
    cid: str,
    ops: list[str],
    *,
    intents: list[str] | None = None,
    required: list[str] | None = None,
    safety: str = "read-only",
    residency: str = "",
    domains: list[str] | None = None,
    deps: list[str] | None = None,
    mutex: list[str] | None = None,
    description: str = "",
) -> dict[str, Any]:
    props = {r: {"type": "string"} for r in (required or [])}
    return {
        "capability_id": cid,
        "kind": "tool",
        "version": "1.0.0",
        "operation_types": ops,
        "serves_intents": intents or [],
        "input_schema": {"type": "object", "properties": props, "required": required or []},
        "output_schema": {"type": "object"},
        "produces_facts": True,
        "dependencies": deps or [],
        "mutually_exclusive_with": mutex or [],
        "data_residency": residency,
        "allowed_policy_domains": domains or [],
        "cost_profile": {"tokens": 100, "latency_ms": 200, "safety_class": safety},
        "metadata": {"description": description},
    }


class TestCapabilityDescriptor:
    def test_from_dict_normalises_operations(self) -> None:
        d = CapabilityDescriptor.from_dict(_desc("c", ["RETRIEVE", "analyse"]))
        assert STLOperation.RETRIEVE in d.operation_types
        assert STLOperation.ANALYSE in d.operation_types

    def test_legacy_evaluate_maps_to_verify(self) -> None:
        d = CapabilityDescriptor.from_dict(_desc("c", ["EVALUATE"]))
        assert d.operation_types == [STLOperation.VERIFY]

    def test_unknown_operation_is_skipped(self) -> None:
        d = CapabilityDescriptor.from_dict(_desc("c", ["RETRIEVE", "FLY_TO_MOON"]))
        assert d.operation_types == [STLOperation.RETRIEVE]

    def test_validate_clean(self) -> None:
        d = CapabilityDescriptor.from_dict(_desc("c", ["RETRIEVE"]))
        assert d.validate() == []

    def test_validate_missing_operation(self) -> None:
        d = CapabilityDescriptor.from_dict(_desc("c", []))
        assert any("operation_types" in e for e in d.validate())

    def test_to_dict_round_trip(self) -> None:
        original = CapabilityDescriptor.from_dict(_desc("c", ["RETRIEVE", "VERIFY"], intents=["x"]))
        rebuilt = CapabilityDescriptor.from_dict(original.to_dict())
        assert rebuilt.capability_id == "c"
        assert rebuilt.operation_types == original.operation_types
        assert rebuilt.cost_profile.safety_class == SafetyClass.READ_ONLY

    def test_serves_operation(self) -> None:
        d = CapabilityDescriptor.from_dict(_desc("c", ["RETRIEVE"]))
        assert d.serves_operation(STLOperation.RETRIEVE)
        assert not d.serves_operation(STLOperation.GENERATE)


class TestPolicyContext:
    def test_blocklist(self) -> None:
        cap = CapabilityDescriptor.from_dict(_desc("web", ["RETRIEVE"]))
        ok, reason = PolicyContext(blocklist={"web"}).evaluate(cap)
        assert not ok and reason == "blocklist"

    def test_allowlist_excludes(self) -> None:
        cap = CapabilityDescriptor.from_dict(_desc("web", ["RETRIEVE"]))
        ok, reason = PolicyContext(allowlist={"other"}).evaluate(cap)
        assert not ok and reason == "not-in-allowlist"

    def test_blocked_safety_class(self) -> None:
        cap = CapabilityDescriptor.from_dict(_desc("rm", ["TRANSFORM"], safety="destructive"))
        ok, reason = PolicyContext(blocked_safety_classes={SafetyClass.DESTRUCTIVE}).evaluate(cap)
        assert not ok and "safety-class-blocked" in reason

    def test_data_residency_conflict(self) -> None:
        cap = CapabilityDescriptor.from_dict(_desc("us", ["RETRIEVE"], residency="US"))
        ok, reason = PolicyContext(data_residency="EU").evaluate(cap)
        assert not ok and "data-residency-conflict" in reason

    def test_policy_domain_mismatch(self) -> None:
        cap = CapabilityDescriptor.from_dict(_desc("c", ["RETRIEVE"], domains=["legal"]))
        ok, reason = PolicyContext(policy_domains={"medical"}).evaluate(cap)
        assert not ok and reason == "policy-domain-mismatch"

    def test_allows_when_unconstrained(self) -> None:
        cap = CapabilityDescriptor.from_dict(_desc("c", ["RETRIEVE"]))
        ok, _ = PolicyContext().evaluate(cap)
        assert ok


class TestToolCapabilityFabric:
    def _fabric(self, n: int, op: str = "RETRIEVE") -> ToolCapabilityFabric:
        tcf = ToolCapabilityFabric()
        for i in range(n):
            tcf.register_dict(_desc(f"tool_{i}", [op], intents=[f"intent_{i}"]))
        return tcf

    def test_register_and_retrieve(self) -> None:
        tcf = self._fabric(3)
        assert len(tcf.all()) == 3
        assert len(tcf.retrieve(STLOperation.RETRIEVE)) == 3
        assert tcf.retrieve(STLOperation.GENERATE) == []

    def test_invalid_descriptor_raises(self) -> None:
        tcf = ToolCapabilityFabric()
        with pytest.raises(ValueError):
            tcf.register_dict(_desc("bad", []))  # no operation_types

    def test_topk_small_local(self) -> None:
        tcf = self._fabric(5)
        sel = tcf.select(STLOperation.RETRIEVE, profile=CapabilityProfile.SMALL_LOCAL)
        assert len(sel.selected) == 2
        assert sel.max_k == 2

    def test_topk_capable_local(self) -> None:
        tcf = self._fabric(6)
        sel = tcf.select(STLOperation.RETRIEVE, profile=CapabilityProfile.CAPABLE_LOCAL)
        assert len(sel.selected) == 4

    def test_topk_frontier_caps_at_available(self) -> None:
        tcf = self._fabric(3)
        sel = tcf.select(STLOperation.RETRIEVE, profile=CapabilityProfile.FRONTIER)
        assert len(sel.selected) == 3  # only 3 exist, max is 7

    def test_policy_rejection_recorded(self) -> None:
        tcf = ToolCapabilityFabric()
        tcf.register_dict(_desc("safe", ["RETRIEVE"]))
        tcf.register_dict(_desc("danger", ["RETRIEVE"], safety="destructive"))
        sel = tcf.select(
            STLOperation.RETRIEVE,
            policy=PolicyContext(blocked_safety_classes={SafetyClass.DESTRUCTIVE}),
        )
        assert "safe" in sel.capability_ids
        assert "danger" not in sel.capability_ids
        assert any(cid == "danger" for cid, _ in sel.rejected)

    def test_mutual_exclusion(self) -> None:
        tcf = ToolCapabilityFabric()
        # 'a' wins on the query and excludes 'b'
        tcf.register_dict(_desc("a", ["RETRIEVE"], intents=["alpha"], mutex=["b"], description="alpha"))
        tcf.register_dict(_desc("b", ["RETRIEVE"], intents=["beta"], description="beta"))
        sel = tcf.select(STLOperation.RETRIEVE, "alpha alpha", profile=CapabilityProfile.SMALL_LOCAL)
        assert "a" in sel.capability_ids
        assert "b" not in sel.capability_ids

    def test_dependency_pulled_in(self) -> None:
        tcf = ToolCapabilityFabric()
        tcf.register_dict(_desc("dep", ["RETRIEVE"]))            # the dependency
        tcf.register_dict(_desc("main", ["ANALYSE"], deps=["dep"]))
        sel = tcf.select(STLOperation.ANALYSE, profile=CapabilityProfile.SMALL_LOCAL)
        ids = sel.capability_ids
        assert "main" in ids and "dep" in ids
        assert ids.index("dep") < ids.index("main")  # dependency offered first

    def test_query_relevance_ranks_first(self) -> None:
        tcf = ToolCapabilityFabric()
        tcf.register_dict(_desc("records", ["RETRIEVE"], intents=["find_records"],
                                description="find user records in the database"))
        tcf.register_dict(_desc("weather", ["RETRIEVE"], intents=["weather"],
                                description="get the weather forecast"))
        sel = tcf.select(STLOperation.RETRIEVE, "find the user records",
                         profile=CapabilityProfile.SMALL_LOCAL)
        assert sel.capability_ids[0] == "records"

    def test_max_capabilities_by_profile(self) -> None:
        assert max_capabilities(CapabilityProfile.SMALL_LOCAL) == 2
        assert max_capabilities(CapabilityProfile.CAPABLE_LOCAL) == 4
        assert max_capabilities(CapabilityProfile.FRONTIER) == 7


class TestCapabilityExecutor:
    def test_validate_missing_required(self) -> None:
        d = CapabilityDescriptor.from_dict(_desc("c", ["RETRIEVE"], required=["topic"]))
        assert any("topic" in e for e in validate_arguments(d, {}))

    def test_validate_type_mismatch(self) -> None:
        d = CapabilityDescriptor.from_dict(
            {**_desc("c", ["RETRIEVE"]), "input_schema": {
                "type": "object", "properties": {"n": {"type": "integer"}}, "required": []}}
        )
        assert any("n" in e for e in validate_arguments(d, {"n": "not-an-int"}))
        assert any("n" in e for e in validate_arguments(d, {"n": True}))  # bool != integer
        assert validate_arguments(d, {"n": 5}) == []

    def test_execute_ok_with_extractor(self) -> None:
        d = CapabilityDescriptor.from_dict(_desc("nmap", ["RETRIEVE"], required=["target"]))
        ex = CapabilityExecutor()
        ex.register_impl(
            "nmap",
            lambda args: f"raw scan of {args['target']}: 22/tcp open",
            extractor=lambda raw, args: {"open_ports": [22], "target": args["target"]},
        )
        res = ex.execute(d, {"target": "10.0.0.1"}, STLOperation.RETRIEVE, window_id="w1")
        assert res.ok
        assert res.observation is not None
        assert res.observation.payload == {"open_ports": [22], "target": "10.0.0.1"}
        assert res.observation.window_id == "w1"
        assert res.raw_output.startswith("raw scan")
        body = res.observation.to_dict()
        assert body["fact_type"] == "TOOL_OBSERVATION"
        assert body["operation_type"] == "RETRIEVE"
        assert body["provenance"]["source_type"] == "TOOL"

    def test_execute_validation_failed(self) -> None:
        d = CapabilityDescriptor.from_dict(_desc("c", ["RETRIEVE"], required=["target"]))
        ex = CapabilityExecutor()
        ex.register_impl("c", lambda args: "ok")
        res = ex.execute(d, {}, STLOperation.RETRIEVE)
        assert res.status is ExecutionStatus.VALIDATION_FAILED
        assert res.observation is None

    def test_execute_error_contained(self) -> None:
        d = CapabilityDescriptor.from_dict(_desc("c", ["RETRIEVE"]))
        ex = CapabilityExecutor()
        def _boom(args: dict[str, Any]) -> Any:
            raise RuntimeError("tool crashed")
        ex.register_impl("c", _boom)
        res = ex.execute(d, {}, STLOperation.RETRIEVE)
        assert res.status is ExecutionStatus.ERROR
        assert any("tool crashed" in e for e in res.errors)

    def test_execute_not_registered(self) -> None:
        d = CapabilityDescriptor.from_dict(_desc("ghost", ["RETRIEVE"]))
        res = CapabilityExecutor().execute(d, {}, STLOperation.RETRIEVE)
        assert res.status is ExecutionStatus.NOT_REGISTERED
