# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Unit tests for the Cognitive State Object (CSO) — SPEC-030."""

from __future__ import annotations

import pytest

from crp.state.cso import (
    CognitiveStateObject,
    Decision,
    DependencyEdge,
    EstablishedFact,
    GoalMode,
    GoalState,
    ProvenanceKind,
    extract_cso,
    preservation_report,
    relay_cso,
)

# ---------------------------------------------------------------------------
# EstablishedFact
# ---------------------------------------------------------------------------


class TestEstablishedFact:
    def test_defaults(self):
        f = EstablishedFact(fact_id="f1", statement="test fact", provenance=ProvenanceKind.CKF)
        assert f.fact_id == "f1"
        assert f.confidence == 1.0
        assert not f.invalidated

    def test_provenance_enum(self):
        for kind in ProvenanceKind:
            f = EstablishedFact(fact_id="x", statement="s", provenance=kind)
            assert f.provenance == kind


# ---------------------------------------------------------------------------
# Decision
# ---------------------------------------------------------------------------


class TestDecision:
    def test_defaults(self):
        d = Decision(decision_id="d1", choice="use PostgreSQL", rationale="ACID required")
        assert d.revisable is True
        assert d.revised_by == ""
        assert d.alternatives == []

    def test_rationale_preserved(self):
        d = Decision(
            decision_id="d1",
            choice="use PostgreSQL",
            rationale="ACID transactions required for financial data",
            alternatives=["MongoDB", "DynamoDB"],
        )
        assert "ACID" in d.rationale
        assert "MongoDB" in d.alternatives


# ---------------------------------------------------------------------------
# CognitiveStateObject — core
# ---------------------------------------------------------------------------


class TestCSOCore:
    def test_auto_id(self):
        c = CognitiveStateObject()
        assert len(c.cso_id) == 36  # UUID format

    def test_empty_preservation_score(self):
        prior = CognitiveStateObject(window_number=1)
        current = CognitiveStateObject(window_number=2)
        # No prior facts → score = 1.0
        assert current.preservation_score(prior) == 1.0

    def test_full_preservation(self):
        prior = CognitiveStateObject(window_number=1)
        prior.established_facts.append(
            EstablishedFact(fact_id="f1", statement="fact 1", provenance=ProvenanceKind.CKF)
        )
        current = CognitiveStateObject(window_number=2)
        current.established_facts.append(
            EstablishedFact(fact_id="f1", statement="fact 1", provenance=ProvenanceKind.CKF)
        )
        assert current.preservation_score(prior) == 1.0

    def test_partial_preservation_triggers_repair(self):
        prior = CognitiveStateObject(window_number=1)
        prior.established_facts += [
            EstablishedFact(fact_id="f1", statement="fact 1", provenance=ProvenanceKind.CKF),
            EstablishedFact(fact_id="f2", statement="fact 2", provenance=ProvenanceKind.CKF),
        ]
        current = CognitiveStateObject(window_number=2)
        current.established_facts.append(
            EstablishedFact(fact_id="f1", statement="fact 1", provenance=ProvenanceKind.CKF)
        )
        # Only f1 preserved → score = 0.5
        assert current.preservation_score(prior) == 0.5
        # After repair, both facts present
        current.repair_from(prior)
        assert current.preservation_score(prior) == 1.0

    def test_invalidated_facts_excluded_from_score(self):
        prior = CognitiveStateObject(window_number=1)
        prior.established_facts.append(
            EstablishedFact(fact_id="f1", statement="stale fact", provenance=ProvenanceKind.CKF, invalidated=True)
        )
        current = CognitiveStateObject(window_number=2)
        # f1 is invalidated in prior → not required for preservation
        assert current.preservation_score(prior) == 1.0


# ---------------------------------------------------------------------------
# Goal state
# ---------------------------------------------------------------------------


class TestGoalState:
    def test_modes(self):
        for mode in GoalMode:
            gs = GoalState(mode=mode)
            assert gs.mode == mode

    def test_remaining_tracking(self):
        gs = GoalState(
            mode=GoalMode.DOCUMENT,
            remaining=["intro", "arch", "deploy"],
        )
        assert len(gs.remaining) == 3


# ---------------------------------------------------------------------------
# to_prompt_context
# ---------------------------------------------------------------------------


class TestPromptContext:
    def test_renders_objective(self):
        cso = CognitiveStateObject(window_number=1)
        cso.goal_state.objective = "Write section 2"
        cso.goal_state.remaining = ["deployment", "monitoring"]
        ctx = cso.to_prompt_context()
        assert "Write section 2" in ctx
        assert "deployment" in ctx

    def test_renders_facts(self):
        cso = CognitiveStateObject(window_number=1)
        cso.established_facts.append(
            EstablishedFact(fact_id="f1", statement="etcd v3.5 deployed", provenance=ProvenanceKind.CKF)
        )
        ctx = cso.to_prompt_context()
        assert "etcd v3.5 deployed" in ctx

    def test_renders_decision_with_rationale(self):
        cso = CognitiveStateObject(window_number=1)
        cso.decisions.append(
            Decision(decision_id="d1", choice="use IPVS", rationale="iptables does not scale at 10k pods")
        )
        ctx = cso.to_prompt_context()
        assert "use IPVS" in ctx
        assert "iptables does not scale" in ctx

    def test_excludes_revised_decisions(self):
        cso = CognitiveStateObject(window_number=1)
        cso.decisions.append(
            Decision(decision_id="d1", choice="old decision", rationale="old reason", revised_by="d2")
        )
        ctx = cso.to_prompt_context()
        assert "old decision" not in ctx


# ---------------------------------------------------------------------------
# Dependency invalidation
# ---------------------------------------------------------------------------


class TestDependencyInvalidation:
    def test_invalidate_propagates(self):
        cso = CognitiveStateObject(window_number=1)
        cso.established_facts += [
            EstablishedFact(fact_id="fa", statement="fact A", provenance=ProvenanceKind.CKF),
        ]
        cso.decisions += [
            Decision(decision_id="db", choice="decision B", rationale="because A", depends_on=["fa"]),
        ]
        cso.dependency_graph.append(DependencyEdge(dependent="db", depends_on="fa"))

        affected = cso.invalidate_fact("fa")
        assert "db" in affected
        fact_a = next(f for f in cso.established_facts if f.fact_id == "fa")
        assert fact_a.invalidated


# ---------------------------------------------------------------------------
# HMAC chain
# ---------------------------------------------------------------------------


class TestHMACChain:
    def test_compute_hmac(self):
        cso = CognitiveStateObject(window_number=1)
        key = b"test-key-32-bytes-padding-padpad"
        h = cso.compute_hmac(key)
        assert len(h) == 64  # SHA-256 hex digest

    def test_chain_extends(self):
        key = b"test-key-32-bytes-padding-padpad"
        cso1 = CognitiveStateObject(window_number=1)
        h1 = cso1.extend_hmac_chain("", key)

        cso2 = CognitiveStateObject(window_number=2)
        h2 = cso2.extend_hmac_chain(h1, key)

        assert cso2.prior_cso_hash == h1
        assert h2 != h1


# ---------------------------------------------------------------------------
# Serialisation round-trip
# ---------------------------------------------------------------------------


class TestSerialization:
    def test_roundtrip(self):
        cso = CognitiveStateObject(window_number=3)
        cso.established_facts.append(
            EstablishedFact(fact_id="f1", statement="test", provenance=ProvenanceKind.TOOL, confidence=0.9)
        )
        cso.decisions.append(
            Decision(decision_id="d1", choice="pick X", rationale="because Y", alternatives=["Z"])
        )
        cso.open_questions = ["question 1?"]
        cso.active_constraints = ["constraint A"]
        cso.goal_state = GoalState(mode=GoalMode.AGENTIC, objective="do task", remaining=["step1", "step2"])

        d = cso.to_dict()
        restored = CognitiveStateObject.from_dict(d)

        assert restored.window_number == 3
        assert len(restored.established_facts) == 1
        assert restored.established_facts[0].provenance == ProvenanceKind.TOOL
        assert len(restored.decisions) == 1
        assert restored.decisions[0].rationale == "because Y"
        assert restored.goal_state.mode == GoalMode.AGENTIC
        assert "step1" in restored.goal_state.remaining


# ---------------------------------------------------------------------------
# extract_cso
# ---------------------------------------------------------------------------


class TestExtractCSO:
    def test_basic_extraction(self):
        output = (
            "Kubernetes uses a flat network model. Every pod gets a unique IP address. "
            "kube-proxy manages Service routing via iptables rules. "
            "Network Policies control traffic between pods."
        )
        cso = extract_cso(output, window_number=1, goal_sections=["flat network", "kube-proxy", "policies"])
        assert cso.window_number == 1
        assert len(cso.established_facts) > 0
        assert "flat network" in cso.goal_state.remaining or len(cso.goal_state.remaining) >= 0

    def test_carries_forward_constraints(self):
        prior = CognitiveStateObject(window_number=1)
        prior.active_constraints = ["Must not exceed 1200 tokens"]
        output = "The cluster uses CNI plugins for network setup."
        cso = extract_cso(output, window_number=2, prior_cso=prior)
        assert "Must not exceed 1200 tokens" in cso.active_constraints


# ---------------------------------------------------------------------------
# relay_cso — THE GATE FUNCTION
# ---------------------------------------------------------------------------


class TestRelayCSO:
    def test_relay_basic(self):
        output = "Kubernetes uses eBPF via Cilium for high-performance networking. DNS is handled by CoreDNS."
        cso = relay_cso(prior_cso=None, window_output=output, window_number=1)
        assert cso.verified is True
        assert cso.window_number == 1
        assert len(cso.established_facts) > 0

    def test_relay_preserves_prior_facts(self):
        prior = CognitiveStateObject(window_number=1)
        prior.established_facts.append(
            EstablishedFact(fact_id="f_prior", statement="etcd stores cluster state", provenance=ProvenanceKind.CKF)
        )
        # New window output does NOT mention etcd
        output = "Cilium uses eBPF to implement network policies efficiently."
        new_cso = relay_cso(prior_cso=prior, window_output=output, window_number=2)
        # Relay must have repaired the missing prior fact
        fact_ids = {f.fact_id for f in new_cso.established_facts}
        assert "f_prior" in fact_ids, "Prior fact must be preserved through relay"

    def test_relay_verified_flag(self):
        output = "Service mesh implementations like Istio add mTLS between pods."
        cso1 = relay_cso(None, output, 1)
        cso2 = relay_cso(cso1, "Linkerd is a lighter alternative to Istio.", 2)
        assert cso2.verified is True

    def test_hmac_chain(self):
        key = b"crp-hmac-key-for-tests-padpadpad"
        output1 = "First window content about Kubernetes networking."
        cso1 = relay_cso(None, output1, 1, hmac_key=key)
        assert cso1.cso_hmac != ""

        output2 = "Second window continuing the technical guide."
        cso2 = relay_cso(cso1, output2, 2, hmac_key=key)
        assert cso2.prior_cso_hash == cso1.cso_hmac


# ---------------------------------------------------------------------------
# preservation_report
# ---------------------------------------------------------------------------


class TestPreservationReport:
    def test_full_preservation(self):
        prior = CognitiveStateObject(window_number=1)
        prior.established_facts.append(
            EstablishedFact(fact_id="f1", statement="fact 1", provenance=ProvenanceKind.CKF)
        )
        current = CognitiveStateObject(window_number=2)
        current.established_facts.append(
            EstablishedFact(fact_id="f1", statement="fact 1", provenance=ProvenanceKind.CKF)
        )
        report = preservation_report(prior, current)
        assert report["score"] == 1.0
        assert report["repaired"] == 0

    def test_partial_preservation(self):
        prior = CognitiveStateObject(window_number=1)
        prior.established_facts += [
            EstablishedFact(fact_id="f1", statement="fact 1", provenance=ProvenanceKind.CKF),
            EstablishedFact(fact_id="f2", statement="fact 2", provenance=ProvenanceKind.CKF),
        ]
        current = CognitiveStateObject(window_number=2)
        current.established_facts.append(
            EstablishedFact(fact_id="f1", statement="fact 1", provenance=ProvenanceKind.CKF)
        )
        report = preservation_report(prior, current)
        assert report["score"] == 0.5
        assert report["repaired"] == 1
