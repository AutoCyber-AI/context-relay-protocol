# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Tests for Predictive Positioning / World-Model Induction (SPEC-051)."""

from __future__ import annotations

import pytest

from crp.extraction.types import Fact, FactGraph
from crp.pp import (
    CausalEdge,
    Rule,
    Transition,
    WorldModel,
    add_causal_edge,
    causal_upstream,
    guarded_dispatch,
    induce_rules,
)


class TestInduction:
    def test_induce_simple_rule(self):
        transitions = [
            Transition(pre={"host_up": True}, action="port_scan", post={"ports": [22, 80]}),
            Transition(pre={"host_up": True}, action="port_scan", post={"ports": [22, 80]}),
            Transition(pre={"host_up": False}, action="port_scan", post={"ports": []}),
        ]
        rules = induce_rules(transitions, min_support=2, min_conf=1.0)
        assert len(rules) == 1
        rule = rules[0]
        assert rule.action == "port_scan"
        assert rule.condition == {"host_up": True}
        assert rule.predicts == {"ports": [22, 80]}
        assert rule.support == 2
        assert rule.confidence == 1.0

    def test_insufficient_support(self):
        transitions = [
            Transition(pre={"x": 1}, action="a", post={"y": 2}),
        ]
        assert induce_rules(transitions, min_support=2) == []


class TestWorldModel:
    def test_predict_matching_rule(self):
        rule = Rule(
            action="port_scan",
            condition={"host_up": True},
            predicts={"ports": [22]},
            support=5,
            confidence=0.9,
        )
        world = WorldModel([rule])
        pred = world.predict({"host_up": True}, "port_scan")
        assert pred is not None
        assert pred["predicted"] == {"ports": [22]}
        assert pred["confidence"] == 0.9
        assert pred["support"] == 5

    def test_no_match_returns_none(self):
        rule = Rule(action="a", condition={"x": 1}, predicts={"y": 2}, support=2, confidence=1.0)
        world = WorldModel([rule])
        assert world.predict({"x": 2}, "a") is None

    def test_best_confidence_wins(self):
        rules = [
            Rule(action="a", condition={"x": 1}, predicts={"y": 1}, support=2, confidence=0.6),
            Rule(action="a", condition={"x": 1}, predicts={"y": 2}, support=5, confidence=0.9),
        ]
        world = WorldModel(rules)
        pred = world.predict({"x": 1}, "a")
        assert pred["predicted"] == {"y": 2}


class TestCausalCKF:
    def test_add_causal_edge_and_walk_upstream(self):
        graph = FactGraph()
        f1 = Fact(id="f1", text="open port 22")
        f2 = Fact(id="f2", text="ssh accessible")
        graph.add_fact(f1)
        graph.add_fact(f2)

        add_causal_edge(graph, f1, f2, CausalEdge.CAUSES, textual_conf=0.7)
        upstream = causal_upstream(graph, "f2", max_depth=3)
        assert len(upstream) == 1
        assert upstream[0]["cause"] == "f1"
        assert upstream[0]["effect"] == "f2"
        assert upstream[0]["kind"] == "causes"

    def test_prevents_edges_not_followed_by_default(self):
        graph = FactGraph()
        f1 = Fact(id="f1", text="firewall rule")
        f2 = Fact(id="f2", text="exploit succeeds")
        graph.add_fact(f1)
        graph.add_fact(f2)
        add_causal_edge(graph, f1, f2, CausalEdge.PREVENTS, textual_conf=0.8)
        upstream = causal_upstream(graph, "f2", max_depth=3)
        assert upstream == []

        upstream_prevents = causal_upstream(
            graph, "f2", max_depth=3, kinds={CausalEdge.PREVENTS.value}
        )
        assert len(upstream_prevents) == 1


class TestGuardedDispatch:
    def test_high_risk_blocked_on_predicted_violation(self):
        rule = Rule(
            action="delete_user",
            condition={"admin": False},
            predicts={"account_gone": True},
            support=10,
            confidence=0.9,
        )
        world = WorldModel([rule])

        class Policy:
            simulate_risk_levels = {"HIGH"}
            sim_confidence_floor = 0.75

            def check_predicted_outcome(self, predicted):
                if predicted.get("account_gone"):
                    return "irreversible_data_loss"
                return None

        def execute(state, action, prediction):
            return {"status": "done"}

        def checkpoint(reason, prediction, state):
            return {"status": "checkpoint", "reason": reason}

        result = guarded_dispatch(
            state={"admin": False},
            action="delete_user",
            risk="HIGH",
            world=world,
            policy=Policy(),
            execute_fn=execute,
            checkpoint_fn=checkpoint,
        )
        assert result["status"] == "checkpoint"
        assert "irreversible_data_loss" in result["reason"]
        assert result["_simulation"]["allowed"] is False

    def test_low_risk_proceeds_without_prediction(self):
        world = WorldModel([])

        class Policy:
            simulate_risk_levels = {"HIGH"}
            sim_confidence_floor = 0.75

            def check_predicted_outcome(self, predicted):
                return None

        def execute(state, action, prediction):
            return {"status": "done"}

        def checkpoint(reason, prediction, state):
            return {"status": "checkpoint"}

        result = guarded_dispatch(
            state={},
            action="read",
            risk="LOW",
            world=world,
            policy=Policy(),
            execute_fn=execute,
            checkpoint_fn=checkpoint,
        )
        assert result["status"] == "done"
        assert result["_simulation"]["executed"] is True

    def test_high_risk_proceeds_when_no_rule_matches(self):
        world = WorldModel([])

        class Policy:
            simulate_risk_levels = {"HIGH"}
            sim_confidence_floor = 0.75

            def check_predicted_outcome(self, predicted):
                return "bad"

        def execute(state, action, prediction):
            return {"status": "done"}

        def checkpoint(reason, prediction, state):
            return {"status": "checkpoint"}

        result = guarded_dispatch(
            state={},
            action="unknown",
            risk="HIGH",
            world=world,
            policy=Policy(),
            execute_fn=execute,
            checkpoint_fn=checkpoint,
        )
        assert result["status"] == "done"
        assert result["_simulation"]["prediction"] is None
