# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Tests for the Quality-Tier-Supervised Router (SPEC-050)."""

from __future__ import annotations

import pytest

from crp.qsr import (
    CapabilityProfile,
    LearnedRouter,
    RoutingExample,
    RoutingTask,
    adapt_schema,
    harvest,
    run_with_escalation,
)


class TestCapabilityProfile:
    def test_score_for_known_kind(self):
        p = CapabilityProfile("test", competence={"code": 0.9})
        assert p.score_for("code") == 0.9

    def test_score_for_unknown_kind_defaults(self):
        p = CapabilityProfile("test", competence={})
        assert p.score_for("anything") == 0.5


class TestHarvest:
    def test_harvest_filters_dispatch_complete(self):
        records = [
            {"stage": "dispatch_complete", "task": {"kind": "code", "complexity": "REASONING_DENSE", "est_tokens": 500, "depth": "thorough", "schema_depth": 4, "tools": ["a"]}, "decision": {"model_id": "qwen3-coder-7b"}, "result": {"tier": "A", "vr_ratio": 0.95, "latency_ms": 120, "cost": 0.0}},
            {"stage": "injection_warning", "foo": "bar"},
        ]
        examples = harvest(records)
        assert len(examples) == 1
        ex = examples[0]
        assert ex.task_kind == "code"
        assert ex.model_id == "qwen3-coder-7b"
        assert ex.quality_tier == "A"
        assert ex.tool_count == 1


class TestLearnedRouter:
    def test_cold_start_routes_by_profile(self):
        router = LearnedRouter()
        task = RoutingTask(kind="math", schema_depth=2)
        assert router.route(task) == "phi4-math-4b"

    def test_schema_depth_eligibility_filter(self):
        router = LearnedRouter()
        task = RoutingTask(kind="code", schema_depth=5)
        # gemma3-4b (ceiling 2) and phi4-math-4b (ceiling 3) are ineligible.
        assert router.route(task) == "qwen3-coder-7b"

    def test_cold_start_no_eligible_falls_back_to_largest_ceiling(self):
        fleet = {
            "small": CapabilityProfile("small", schema_complexity_ceiling=1),
        }
        router = LearnedRouter(fleet=fleet)
        task = RoutingTask(kind="prose", schema_depth=5)
        assert router.route(task) == "small"

    def test_train_requires_threshold_examples(self):
        router = LearnedRouter(min_train_examples=10)
        examples = [
            RoutingExample(
                task_kind="code",
                complexity="REASONING_DENSE",
                est_tokens=100,
                tool_count=0,
                depth="standard",
                model_id="qwen3-coder-7b",
                quality_tier="A",
            )
            for _ in range(5)
        ]
        assert router.train(examples) is False


class TestSchemaAdapt:
    def test_flatten_nested_beyond_ceiling(self):
        schema = {
            "type": "object",
            "properties": {
                "user": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "address": {
                            "type": "object",
                            "properties": {
                                "city": {"type": "string"},
                            },
                        },
                    },
                },
            },
        }
        adapted = adapt_schema(schema, ceiling=1)
        props = adapted["properties"]
        assert "user.name" in props
        assert "user.address" in props
        assert props["user.address"]["type"] == "string"

    def test_no_change_for_non_object(self):
        assert adapt_schema({"type": "string"}, ceiling=1) == {"type": "string"}


class TestEscalation:
    def test_no_escalation_when_quality_ok(self):
        calls = []

        def execute(task, model_id):
            calls.append(model_id)
            return {"tier": "A", "vr_ratio": 0.95}

        policy = {"escalate_on": {"tier_below": "B", "vr_ratio_below": 0.9}, "max_rungs": 2}
        task = RoutingTask(kind="prose")
        result = run_with_escalation(task, execute, policy)
        assert result["escalated"] is False
        assert len(calls) == 1

    def test_escalates_on_low_tier(self):
        calls = []

        def execute(task, model_id):
            calls.append(model_id)
            return {"tier": "C", "vr_ratio": 0.95}

        policy = {"escalate_on": {"tier_below": "B", "vr_ratio_below": 0.9}, "max_rungs": 2}
        task = RoutingTask(kind="prose")
        result = run_with_escalation(task, execute, policy)
        assert result["escalated"] is True
        assert len(calls) == 3  # initial + up to 2 escalation rungs

    def test_respects_max_rungs(self):
        calls = []

        def execute(task, model_id):
            calls.append(model_id)
            return {"tier": "D", "vr_ratio": 0.5}

        policy = {"escalate_on": {"tier_below": "B", "vr_ratio_below": 0.9}, "max_rungs": 1}
        task = RoutingTask(kind="prose")
        result = run_with_escalation(task, execute, policy)
        assert result["escalated"] is True
        assert len(calls) == 2  # first + one escalation
