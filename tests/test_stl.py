# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Tests for Semantic Task Layer — positioning, not injection (SPEC-031)."""

from __future__ import annotations

from crp.stl.classifier import STLOperation, classify_operations
from crp.stl.depth_model import DepthLevel, negotiate_depth, renegotiate_depth
from crp.stl.frame_builder import OperationFrame, build_operation_frame
from crp.stl.goal_compass import GoalCompass, build_goal_compass
from crp.stl.orchestrator import STLResult, stl_execute


class TestOperationClassifier:
    def test_classify_retrieve(self) -> None:
        ops = classify_operations("what is the capital of France")
        assert STLOperation.RETRIEVE in ops

    def test_classify_compare(self) -> None:
        ops = classify_operations("compare Kubernetes and Docker Swarm")
        assert STLOperation.COMPARE in ops

    def test_classify_generate(self) -> None:
        ops = classify_operations("write a poem about autumn")
        assert STLOperation.GENERATE in ops

    def test_classify_analyse(self) -> None:
        ops = classify_operations("analyse the causes of the error")
        assert STLOperation.ANALYSE in ops

    def test_classify_clarify(self) -> None:
        ops = classify_operations("can you clarify what you meant")
        assert STLOperation.CLARIFY in ops

    def test_default_to_generate(self) -> None:
        ops = classify_operations("xyz abc 123")
        assert ops == [STLOperation.GENERATE]


class TestDepthModel:
    def test_propose_d1_for_brief(self) -> None:
        depth, meta = negotiate_depth("briefly tell me", [STLOperation.RETRIEVE])
        assert depth == DepthLevel.D1

    def test_propose_d4_for_thorough(self) -> None:
        depth, meta = negotiate_depth("thorough analysis needed", [STLOperation.ANALYSE])
        assert depth == DepthLevel.D4

    def test_propose_from_complexity(self) -> None:
        depth, meta = negotiate_depth("compare and analyse", [STLOperation.COMPARE, STLOperation.ANALYSE])
        assert depth in (DepthLevel.D3, DepthLevel.D4)

    def test_renegotiate_deepen(self) -> None:
        depth, meta = renegotiate_depth(DepthLevel.D2, "unresolved-complexity")
        assert meta["renegotiated"] is True
        assert meta["direction"] == "deepen"
        assert depth == DepthLevel.D3

    def test_renegotiate_cap(self) -> None:
        depth, meta = renegotiate_depth(DepthLevel.D4, "unresolved-complexity", renegotiation_count=2)
        assert meta["renegotiated"] is False
        assert "capped" in meta["reason"]


class TestGoalCompass:
    def test_build_compass(self) -> None:
        compass = build_goal_compass("ANALYSE", "Write a guide", ["RETRIEVE"])
        assert compass.ultimate_goal
        assert compass.this_operation_serves
        assert compass.fit_constraint

    def test_token_estimate(self) -> None:
        compass = GoalCompass(
            ultimate_goal="Write a guide",
            this_operation_serves="Produce section 2",
            fit_constraint="Match tone",
        )
        assert compass.token_estimate() > 0

    def test_to_prompt_text(self) -> None:
        compass = build_goal_compass("GENERATE", "Draft memo", [])
        text = compass.to_prompt_text()
        assert "Goal context" in text
        assert "Ultimate goal" in text


class TestFrameBuilder:
    def test_build_retrieve_frame(self) -> None:
        frame = build_operation_frame(
            STLOperation.RETRIEVE,
            "what is the speed limit",
            ["Fact A", "Fact B"],
            depth=DepthLevel.D1,
        )
        assert frame.operation_type == STLOperation.RETRIEVE
        assert frame.depth == DepthLevel.D1
        assert "Find and list" in frame.assignment
        assert frame.estimated_tokens > 0

    def test_build_generate_frame(self) -> None:
        frame = build_operation_frame(
            STLOperation.GENERATE,
            "write a haiku",
            [],
            depth=DepthLevel.D2,
        )
        assert frame.operation_type == STLOperation.GENERATE
        assert "produce" in frame.assignment.lower() or "Produce" in frame.assignment

    def test_frame_content_limited(self) -> None:
        facts = [f"Fact {i}" for i in range(20)]
        frame = build_operation_frame(STLOperation.RETRIEVE, "query", facts)
        # Frame should limit facts per operation type
        assert frame.estimated_tokens < 5000


class TestSTLOrchestrator:
    def test_stl_execute_single_op(self) -> None:
        result = stl_execute("what is 2+2", None)
        assert isinstance(result, STLResult)
        assert len(result.operations_executed) >= 1
        assert result.depth_proposed
        assert result.headers
        assert "CRP-STL-Operations" in result.headers

    def test_stl_execute_multi_op(self) -> None:
        result = stl_execute("compare and analyse the two approaches", None)
        assert len(result.operations_executed) >= 2
        assert result.frame_tokens_total > 0
        assert result.injection_equivalent_tokens > 0

    def test_frame_vs_inject_ratio(self) -> None:
        result = stl_execute("write a comprehensive guide", None, context_facts=["f1", "f2", "f3", "f4", "f5"])
        ratio = float(result.headers.get("CRP-STL-Frame-Vs-Inject", "1.0"))
        assert ratio < 1.0  # positioning should be more efficient than injection
