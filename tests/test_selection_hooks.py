"""Conformance: the selection_pre_hook / selection_post_hook seam (SPEC-060).

Audit I-C4: consumers used to source-patch run_positioned to steer tool
selection; the hook seam makes that first-class. These tests pin the
contract: the pre-hook may replace the selection policy, query text,
embedding and frame cap; hook exceptions never break the loop; the
post-hook observes every selection.
"""
import json

import pytest

pytest.importorskip("crp")


def _setup():
    from crp.cognition.phase_machine import Phase, PhasePlan
    from crp.stl.classifier import STLOperation
    from crp.tools.capability_fabric import PolicyContext, ToolCapabilityFabric
    from crp.tools.descriptor import CapabilityDescriptor
    from crp.tools.executor import CapabilityExecutor
    from crp.tools.profiles import CapabilityProfile

    fabric = ToolCapabilityFabric()
    for tid in ("tool_a", "tool_b"):
        fabric.register(CapabilityDescriptor(
            capability_id=tid,
            operation_types=[STLOperation.RETRIEVE],
            serves_intents=[f"intent for {tid}"],
            input_schema={"type": "object",
                          "properties": {"target": {"type": "string"}},
                          "required": ["target"]},
        ))
    executor = CapabilityExecutor()
    executed = []
    for tid in ("tool_a", "tool_b"):
        executor.register_impl(
            tid, lambda args, _t=tid: executed.append(_t) or {
                "ok": True,
                "observation": {"kind": "tool_result", "summary": _t, "payload": _t},
            })
    plan = PhasePlan(phases=[Phase(
        name="recon", prompt="recon",
        operations=[STLOperation.RETRIEVE], tools=["tool_a", "tool_b"], depth="",
    )], loop_until="complete")
    return fabric, executor, executed, plan, PolicyContext, CapabilityProfile


def _model_call(prompt, schema=None):
    if schema:
        enum = schema["properties"]["capability_id"]["enum"]
        return json.dumps({"capability_id": enum[0], "arguments": {"target": "x"}})
    return "prose"


def test_pre_hook_filters_policy_and_sets_query():
    from crp.stl.positioned import run_positioned

    fabric, executor, executed, plan, PolicyContext, CapabilityProfile = _setup()
    seen_queries = []

    def pre_hook(*, op, phase, phase_tools, policy, user_request, phase_guidance):
        assert phase_tools == ["tool_a", "tool_b"]
        return {
            "policy": PolicyContext(allowlist={"tool_a"}),
            "query_text": "hooked query",
            "k": 1,
        }

    def post_hook(*, op, phase, selection):
        seen_queries.append(
            [s.descriptor.capability_id for s in selection.selected])

    run_positioned(
        "do the thing", _model_call, fabric=fabric, executor=executor,
        profile=CapabilityProfile.CAPABLE_LOCAL,
        policy=PolicyContext(authorised_scope={"x"}),
        max_operations=2, phase_plan=plan, final_synthesis=False,
        selection_pre_hook=pre_hook, selection_post_hook=post_hook,
    )

    assert seen_queries, "post hook never fired"
    assert all(ids == ["tool_a"] for ids in seen_queries), seen_queries
    assert executed == ["tool_a"], executed


def test_hook_exceptions_are_advisory():
    from crp.stl.positioned import run_positioned

    fabric, executor, executed, plan, PolicyContext, CapabilityProfile = _setup()

    def boom(**kw):
        raise RuntimeError("hook exploded")

    result = run_positioned(
        "do the thing", _model_call, fabric=fabric, executor=executor,
        profile=CapabilityProfile.CAPABLE_LOCAL,
        policy=PolicyContext(authorised_scope={"x"}),
        max_operations=2, phase_plan=plan, final_synthesis=False,
        selection_pre_hook=boom, selection_post_hook=boom,
    )
    assert executed, "loop broke on hook failure"
    assert result.operations, "no operations recorded"


def test_no_hooks_is_stock_behaviour():
    from crp.stl.positioned import run_positioned

    fabric, executor, executed, plan, PolicyContext, CapabilityProfile = _setup()
    result = run_positioned(
        "do the thing", _model_call, fabric=fabric, executor=executor,
        profile=CapabilityProfile.CAPABLE_LOCAL,
        policy=PolicyContext(authorised_scope={"x"}),
        max_operations=2, phase_plan=plan, final_synthesis=False,
    )
    assert executed
    assert result.operations
