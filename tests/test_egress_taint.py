# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Tests for the egress/information-flow taint rule (CRP-SPEC-050 §3.4).

``PolicyContext.evaluate_invocation`` mediates a single proposed capability
invocation: labelled data may only flow to approved sinks, invocation targets
must be in the authorised scope, and irreversible actions require approval.
"""

from __future__ import annotations

from crp.agent_sdk.policy import Policy
from crp.tools.capability_fabric import (
    CapabilityInvocation,
    GateDecision,
    PolicyContext,
)

SINK = "soc@authorised.example"


def _policy() -> PolicyContext:
    return PolicyContext(
        authorised_scope={"10.0.0.10"},
        approved_sinks={SINK},
    )


class TestEgressTaint:
    def test_labelled_action_to_unapproved_sink_denied(self) -> None:
        policy = PolicyContext(approved_sinks={SINK})  # no scope constraint
        inv = CapabilityInvocation(
            capability_id="email", target="attacker@evil.test", data_labels={"findings"}
        )
        decision, reason = policy.evaluate_invocation(inv)
        assert decision is GateDecision.DENY
        assert reason.startswith("egress-taint:")

    def test_labelled_action_to_approved_sink_allowed(self) -> None:
        policy = PolicyContext(approved_sinks={SINK})  # no scope constraint
        inv = CapabilityInvocation(
            capability_id="email", target=SINK, data_labels={"findings"}
        )
        decision, reason = policy.evaluate_invocation(inv)
        assert decision is GateDecision.ALLOW
        assert reason == ""

    def test_unlabelled_action_unaffected(self) -> None:
        # no scope declared, no labels — a plain send to any address passes
        policy = PolicyContext(approved_sinks={SINK})
        inv = CapabilityInvocation(capability_id="email", target="anyone@example.org")
        decision, _ = policy.evaluate_invocation(inv)
        assert decision is GateDecision.ALLOW

    def test_labels_with_no_approved_sinks_fail_closed(self) -> None:
        # fail-safe default deny: labelled data with nothing approved is denied
        policy = PolicyContext()
        inv = CapabilityInvocation(
            capability_id="email", target=SINK, data_labels={"findings"}
        )
        decision, _ = policy.evaluate_invocation(inv)
        assert decision is GateDecision.DENY


class TestScopeAndApproval:
    def test_target_outside_authorised_scope_denied(self) -> None:
        inv = CapabilityInvocation(capability_id="scan", target="10.9.9.9")
        decision, reason = _policy().evaluate_invocation(inv)
        assert decision is GateDecision.DENY
        assert reason.startswith("out-of-scope:")

    def test_empty_scope_is_unconstrained(self) -> None:
        policy = PolicyContext(approved_sinks={SINK})
        inv = CapabilityInvocation(capability_id="scan", target="10.9.9.9")
        decision, _ = policy.evaluate_invocation(inv)
        assert decision is GateDecision.ALLOW

    def test_irreversible_action_requires_approval(self) -> None:
        inv = CapabilityInvocation(
            capability_id="exploit", target="10.0.0.10", irreversible=True
        )
        decision, reason = _policy().evaluate_invocation(inv)
        assert decision is GateDecision.REQUIRE_APPROVAL
        assert reason == "irreversible-action"

    def test_scope_rule_precedes_taint_rule(self) -> None:
        # out-of-scope AND labelled: scope denial wins (rule order is stable)
        inv = CapabilityInvocation(
            capability_id="email", target="attacker@evil.test", data_labels={"findings"}
        )
        decision, reason = _policy().evaluate_invocation(inv)
        assert decision is GateDecision.DENY
        assert reason.startswith("out-of-scope:")


class TestAgentPolicySurface:
    def test_policy_builder_compiles_scope_and_sinks(self) -> None:
        policy = (
            Policy.strict()
            .scope("10.0.0.10")
            .approve_sinks(SINK)
        )
        ctx = policy.to_policy_context()
        assert ctx.authorised_scope == {"10.0.0.10"}
        assert ctx.approved_sinks == {SINK}

        denied, _ = ctx.evaluate_invocation(
            CapabilityInvocation(
                capability_id="email", target="attacker@evil.test",
                data_labels={"findings"},
            )
        )
        assert denied is GateDecision.DENY

    def test_default_policy_context_invocation_unconstrained(self) -> None:
        ctx = Policy().to_policy_context()
        decision, _ = ctx.evaluate_invocation(
            CapabilityInvocation(capability_id="scan", target="10.1.2.3")
        )
        assert decision is GateDecision.ALLOW
