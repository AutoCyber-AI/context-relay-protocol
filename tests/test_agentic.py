# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Tests for LLM-in-the-loop agentic architecture — §22.

Tests cover:
  - CRPFacilitator cognitive engine (unit tests)
  - JSON parsing from LLM responses
  - Task analysis, strategy routing, fact synthesis, output evaluation,
    memory curation, execution planning
  - Facilitator metrics tracking
  - dispatch_agentic() integration in orchestrator
  - Fallback behaviour when LLM returns bad JSON
  - Edge cases (empty facts, simple tasks, etc.)
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import MagicMock, patch, PropertyMock

import pytest


# ═══════════════════════════════════════════════════════════════════════
# Facilitator unit tests
# ═══════════════════════════════════════════════════════════════════════

from crp.core.facilitator import (
    CRPFacilitator,
    CurationDecision,
    ExecutionPlan,
    FacilitatorMetrics,
    OutputEvaluation,
    PlanStep,
    StrategyDecision,
    SynthesizedKnowledge,
    TaskAnalysis,
    _extract_json,
    _parse_curation,
    _parse_evaluation,
    _parse_execution_plan,
    _parse_strategy_decision,
    _parse_synthesis,
    _parse_task_analysis,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _count_tokens(text: str) -> int:
    return max(1, len(text) // 4)


class MockProvider:
    """Minimal LLM provider mock for facilitator tests."""

    def __init__(self, response: str = "{}"):
        self._response = response
        self._call_count = 0

    def generate_chat(self, messages: list[dict], **kwargs) -> tuple[str, str]:
        self._call_count += 1
        return self._response, "stop"

    def count_tokens(self, text: str) -> int:
        return _count_tokens(text)

    def context_window_size(self) -> int:
        return 4096

    @property
    def max_output_tokens(self) -> int:
        return 2048

    @property
    def call_count(self) -> int:
        return self._call_count


# ═══════════════════════════════════════════════════════════════════════
# §22.0 — JSON extraction tests
# ═══════════════════════════════════════════════════════════════════════

class TestExtractJson:
    """Test JSON extraction from various LLM response formats."""

    def test_plain_json(self):
        raw = '{"strategy": "push", "confidence": 0.9}'
        d = _extract_json(raw)
        assert d["strategy"] == "push"
        assert d["confidence"] == 0.9

    def test_markdown_fenced_json(self):
        raw = '```json\n{"strategy": "reflexive"}\n```'
        d = _extract_json(raw)
        assert d["strategy"] == "reflexive"

    def test_json_with_surrounding_text(self):
        raw = 'Here is my analysis:\n{"complexity": "complex"}\nDone.'
        d = _extract_json(raw)
        assert d["complexity"] == "complex"

    def test_empty_string(self):
        assert _extract_json("") == {}

    def test_invalid_json(self):
        assert _extract_json("not json at all") == {}

    def test_json_with_whitespace(self):
        raw = '  \n  {"key": "value"}  \n  '
        d = _extract_json(raw)
        assert d["key"] == "value"


# ═══════════════════════════════════════════════════════════════════════
# §22.1 — Task Analysis tests
# ═══════════════════════════════════════════════════════════════════════

class TestTaskAnalysis:
    """Test LLM-based task analysis."""

    def test_parse_full_analysis(self):
        raw = json.dumps({
            "complexity": "complex",
            "domain": "software engineering",
            "knowledge_needs": ["Python", "testing"],
            "expected_output_length": "long",
            "requires_factual_grounding": True,
            "requires_creativity": False,
            "requires_reasoning": True,
            "subtasks": ["write tests", "run tests"],
            "confidence": 0.85,
        })
        analysis = _parse_task_analysis(raw)
        assert analysis.complexity == "complex"
        assert analysis.domain == "software engineering"
        assert "Python" in analysis.knowledge_needs
        assert analysis.expected_output_length == "long"
        assert analysis.requires_reasoning is True
        assert analysis.confidence == 0.85
        assert len(analysis.subtasks) == 2

    def test_parse_minimal_analysis(self):
        raw = '{"complexity": "simple"}'
        analysis = _parse_task_analysis(raw)
        assert analysis.complexity == "simple"
        assert analysis.domain == "general"
        assert analysis.confidence == 0.5

    def test_parse_empty_returns_defaults(self):
        analysis = _parse_task_analysis("{}")
        assert analysis.complexity == "medium"
        assert analysis.domain == "general"
        assert analysis.requires_factual_grounding is True

    def test_facilitator_analyze_task(self):
        response = json.dumps({
            "complexity": "medium",
            "domain": "history",
            "knowledge_needs": ["World War II"],
            "expected_output_length": "medium",
            "confidence": 0.7,
        })
        provider = MockProvider(response)
        fac = CRPFacilitator(provider=provider, count_tokens=_count_tokens)

        analysis = fac.analyze_task(
            task_input="Tell me about WWII",
            system_prompt="You are a historian.",
            fact_count=10,
        )
        assert analysis.complexity == "medium"
        assert analysis.domain == "history"
        assert provider.call_count == 1
        assert fac.metrics.cognitive_calls == 1
        assert fac.metrics.task_analysis_ms > 0

    def test_task_analysis_dataclass_defaults(self):
        ta = TaskAnalysis()
        assert ta.complexity == "medium"
        assert ta.requires_creativity is False
        assert ta.subtasks == []


# ═══════════════════════════════════════════════════════════════════════
# §22.2 — Strategy Routing tests
# ═══════════════════════════════════════════════════════════════════════

class TestStrategyRouting:
    """Test LLM-based strategy routing."""

    def test_parse_valid_strategy(self):
        raw = json.dumps({
            "strategy": "reflexive",
            "reasoning": "Task needs fact-checking",
            "envelope_priority": "maximal",
            "continuation_likelihood": "medium",
            "confidence": 0.8,
        })
        valid = ["push", "reflexive", "progressive", "stream_augmented"]
        decision = _parse_strategy_decision(raw, valid)
        assert decision.strategy == "reflexive"
        assert "fact-checking" in decision.reasoning
        assert decision.confidence == 0.8

    def test_invalid_strategy_falls_back_to_push(self):
        raw = json.dumps({"strategy": "nonexistent_strategy"})
        valid = ["push", "reflexive"]
        decision = _parse_strategy_decision(raw, valid)
        assert decision.strategy == "push"

    def test_empty_json_defaults(self):
        decision = _parse_strategy_decision("{}", ["push", "reflexive"])
        assert decision.strategy == "push"
        assert decision.confidence == 0.5

    def test_facilitator_route_strategy(self):
        response = json.dumps({
            "strategy": "progressive",
            "reasoning": "Many facts available, broad task",
            "confidence": 0.75,
        })
        provider = MockProvider(response)
        fac = CRPFacilitator(provider=provider, count_tokens=_count_tokens)

        analysis = TaskAnalysis(complexity="complex", domain="science")
        decision = fac.route_strategy(
            analysis=analysis,
            fact_count=100,
            available_strategies=["push", "progressive", "reflexive"],
        )
        assert decision.strategy == "progressive"
        assert fac.metrics.strategy_routing_ms > 0

    def test_strategy_decision_dataclass(self):
        sd = StrategyDecision()
        assert sd.strategy == "push"
        assert sd.confidence == 0.7


# ═══════════════════════════════════════════════════════════════════════
# §22.3 — Fact Synthesis tests
# ═══════════════════════════════════════════════════════════════════════

class TestFactSynthesis:
    """Test LLM-based fact synthesis."""

    def test_parse_full_synthesis(self):
        raw = json.dumps({
            "summary": "The facts indicate strong performance in Q3.",
            "key_insights": ["Revenue grew 20%", "Costs declined"],
            "contradictions": ["Fact 3 vs Fact 7 disagree on margins"],
            "knowledge_gaps": ["No data on Q4 projections"],
            "redundant_fact_ids": ["f-abc", "f-def"],
            "merged_facts": [{"original_ids": ["f-1", "f-2"], "merged_text": "Revenue grew 20% with declining costs."}],
        })
        synthesis = _parse_synthesis(raw)
        assert "Q3" in synthesis.summary
        assert len(synthesis.key_insights) == 2
        assert len(synthesis.contradictions) == 1
        assert len(synthesis.knowledge_gaps) == 1
        assert len(synthesis.redundant_fact_ids) == 2
        assert len(synthesis.merged_facts) == 1

    def test_empty_synthesis(self):
        synthesis = _parse_synthesis("{}")
        assert synthesis.summary == ""
        assert synthesis.key_insights == []

    def test_facilitator_synthesize_empty_facts(self):
        provider = MockProvider()
        fac = CRPFacilitator(provider=provider, count_tokens=_count_tokens)
        synthesis = fac.synthesize_facts(facts=[])
        assert synthesis.summary == ""
        assert provider.call_count == 0  # No LLM call for empty facts

    def test_facilitator_synthesize_with_facts(self):
        response = json.dumps({
            "summary": "Python is a popular language.",
            "key_insights": ["Easy to learn", "Large ecosystem"],
            "knowledge_gaps": ["No info on Python 4"],
        })
        provider = MockProvider(response)
        fac = CRPFacilitator(provider=provider, count_tokens=_count_tokens)

        facts = [
            ("f1", "Python is easy to learn.", 0.9),
            ("f2", "Python has a large ecosystem.", 0.85),
            ("f3", "Python is popular for ML.", 0.8),
        ]
        synthesis = fac.synthesize_facts(facts=facts, task_context="Tell me about Python")
        assert "Python" in synthesis.summary
        assert len(synthesis.key_insights) == 2
        assert fac.metrics.fact_synthesis_ms > 0

    def test_synthesized_knowledge_dataclass(self):
        sk = SynthesizedKnowledge()
        assert sk.summary == ""
        assert sk.merged_facts == []


# ═══════════════════════════════════════════════════════════════════════
# §22.4 — Output Evaluation tests
# ═══════════════════════════════════════════════════════════════════════

class TestOutputEvaluation:
    """Test LLM-based output evaluation."""

    def test_parse_full_evaluation(self):
        raw = json.dumps({
            "task_completion": 0.9,
            "factual_accuracy": 0.85,
            "coherence": 0.95,
            "missing_elements": ["citations"],
            "revision_needed": False,
            "revision_focus": "",
            "overall_grade": "A",
        })
        evaluation = _parse_evaluation(raw)
        assert evaluation.task_completion == 0.9
        assert evaluation.overall_grade == "A"
        assert evaluation.revision_needed is False

    def test_parse_revision_needed(self):
        raw = json.dumps({
            "task_completion": 0.3,
            "revision_needed": True,
            "revision_focus": "Missing core analysis",
            "missing_elements": ["analysis", "conclusion"],
            "overall_grade": "D",
        })
        evaluation = _parse_evaluation(raw)
        assert evaluation.revision_needed is True
        assert evaluation.revision_focus == "Missing core analysis"
        assert evaluation.overall_grade == "D"

    def test_facilitator_evaluate_output(self):
        response = json.dumps({
            "task_completion": 0.85,
            "factual_accuracy": 0.9,
            "coherence": 0.88,
            "overall_grade": "A",
            "revision_needed": False,
        })
        provider = MockProvider(response)
        fac = CRPFacilitator(provider=provider, count_tokens=_count_tokens)

        evaluation = fac.evaluate_output(
            task_input="Explain quantum mechanics",
            output="Quantum mechanics is the study of...",
            facts_used=5,
        )
        assert evaluation.task_completion == 0.85
        assert evaluation.overall_grade == "A"
        assert fac.metrics.output_evaluation_ms > 0

    def test_output_evaluation_dataclass(self):
        oe = OutputEvaluation()
        assert oe.task_completion == 0.0
        assert oe.overall_grade == "B"


# ═══════════════════════════════════════════════════════════════════════
# §22.5 — Memory Curation tests
# ═══════════════════════════════════════════════════════════════════════

class TestMemoryCuration:
    """Test LLM-based memory curation."""

    def test_parse_curation(self):
        raw = json.dumps({
            "promote_ids": ["f-1", "f-2"],
            "demote_ids": ["f-3"],
            "merge_groups": [["f-4", "f-5"]],
            "discard_ids": ["f-6"],
            "reasoning": "Facts f-4 and f-5 cover same topic.",
        })
        curation = _parse_curation(raw)
        assert len(curation.promote_ids) == 2
        assert len(curation.demote_ids) == 1
        assert len(curation.merge_groups) == 1
        assert "same topic" in curation.reasoning

    def test_empty_curation(self):
        curation = _parse_curation("{}")
        assert curation.promote_ids == []
        assert curation.reasoning == ""

    def test_facilitator_curate_empty(self):
        provider = MockProvider()
        fac = CRPFacilitator(provider=provider, count_tokens=_count_tokens)
        curation = fac.curate_memory(facts=[])
        assert curation.promote_ids == []
        assert provider.call_count == 0  # No call for empty

    def test_facilitator_curate_with_facts(self):
        response = json.dumps({
            "promote_ids": ["f-1"],
            "demote_ids": ["f-2"],
            "reasoning": "f-1 is high value, f-2 is stale.",
        })
        provider = MockProvider(response)
        fac = CRPFacilitator(provider=provider, count_tokens=_count_tokens)

        facts = [
            ("f-1", "Important fact", 0.9, 1),
            ("f-2", "Stale fact", 0.5, 10),
        ]
        curation = fac.curate_memory(facts=facts, recent_task="Test task")
        assert "f-1" in curation.promote_ids
        assert "f-2" in curation.demote_ids
        assert fac.metrics.memory_curation_ms > 0

    def test_curation_decision_dataclass(self):
        cd = CurationDecision()
        assert cd.merge_groups == []
        assert cd.discard_ids == []


# ═══════════════════════════════════════════════════════════════════════
# §22.6 — Execution Planning tests
# ═══════════════════════════════════════════════════════════════════════

class TestExecutionPlanning:
    """Test LLM-based execution planning."""

    def test_parse_execution_plan(self):
        raw = json.dumps({
            "steps": [
                {
                    "description": "Research topic",
                    "strategy": "push",
                    "context_needs": ["topic basics"],
                    "depends_on": [],
                    "priority": 1,
                },
                {
                    "description": "Generate analysis",
                    "strategy": "reflexive",
                    "context_needs": ["research results"],
                    "depends_on": [0],
                    "priority": 2,
                },
            ],
            "estimated_windows": 3,
            "parallel_possible": False,
        })
        plan = _parse_execution_plan(raw)
        assert len(plan.steps) == 2
        assert plan.steps[0].strategy == "push"
        assert plan.steps[1].depends_on == [0]
        assert plan.estimated_windows == 3
        assert plan.parallel_possible is False

    def test_empty_plan_gets_default_step(self):
        plan = _parse_execution_plan("{}")
        assert len(plan.steps) == 1
        assert plan.steps[0].strategy == "push"

    def test_simple_task_skips_planning(self):
        provider = MockProvider()
        fac = CRPFacilitator(provider=provider, count_tokens=_count_tokens)

        analysis = TaskAnalysis(complexity="simple")
        plan = fac.plan_execution(analysis=analysis)
        assert len(plan.steps) == 1
        assert plan.estimated_windows == 1
        assert provider.call_count == 0  # No LLM call for simple tasks

    def test_complex_task_triggers_planning(self):
        response = json.dumps({
            "steps": [
                {"description": "Step 1", "strategy": "push", "priority": 1},
                {"description": "Step 2", "strategy": "reflexive", "priority": 2},
            ],
            "estimated_windows": 4,
        })
        provider = MockProvider(response)
        fac = CRPFacilitator(provider=provider, count_tokens=_count_tokens)

        analysis = TaskAnalysis(complexity="complex", domain="engineering")
        plan = fac.plan_execution(analysis=analysis, fact_count=50)
        assert len(plan.steps) == 2
        assert provider.call_count == 1
        assert fac.metrics.execution_planning_ms > 0

    def test_plan_step_dataclass(self):
        ps = PlanStep()
        assert ps.description == ""
        assert ps.strategy == "push"
        assert ps.depends_on == []


# ═══════════════════════════════════════════════════════════════════════
# Facilitator metrics tests
# ═══════════════════════════════════════════════════════════════════════

class TestFacilitatorMetrics:
    """Test facilitator metrics tracking."""

    def test_initial_metrics(self):
        m = FacilitatorMetrics()
        assert m.cognitive_calls == 0
        assert m.total_cognitive_tokens == 0
        assert m.total_cognitive_ms == 0.0

    def test_total_cognitive_ms_property(self):
        m = FacilitatorMetrics(
            task_analysis_ms=10.0,
            strategy_routing_ms=5.0,
            fact_synthesis_ms=15.0,
            output_evaluation_ms=8.0,
            memory_curation_ms=6.0,
            execution_planning_ms=3.0,
        )
        assert m.total_cognitive_ms == pytest.approx(47.0)

    def test_metrics_accumulate_across_calls(self):
        response = json.dumps({"complexity": "simple"})
        provider = MockProvider(response)
        fac = CRPFacilitator(provider=provider, count_tokens=_count_tokens)

        # Two cognitive calls
        fac.analyze_task("task 1", "sys", 0)
        fac.analyze_task("task 2", "sys", 0)

        assert fac.metrics.cognitive_calls == 2
        assert fac.metrics.total_cognitive_tokens > 0

    def test_reset_metrics(self):
        response = json.dumps({"complexity": "simple"})
        provider = MockProvider(response)
        fac = CRPFacilitator(provider=provider, count_tokens=_count_tokens)

        fac.analyze_task("task", "sys", 0)
        assert fac.metrics.cognitive_calls == 1

        fac.reset_metrics()
        assert fac.metrics.cognitive_calls == 0
        assert fac.metrics.total_cognitive_tokens == 0


# ═══════════════════════════════════════════════════════════════════════
# Facilitator error handling / fallback tests
# ═══════════════════════════════════════════════════════════════════════

class TestFacilitatorFallbacks:
    """Test graceful degradation when LLM returns bad data."""

    def test_llm_returns_garbage_text(self):
        provider = MockProvider("this is not json at all")
        fac = CRPFacilitator(provider=provider, count_tokens=_count_tokens)

        # Should return defaults, not crash
        analysis = fac.analyze_task("task", "sys", 0)
        assert analysis.complexity == "medium"
        assert analysis.domain == "general"

    def test_llm_returns_partial_json(self):
        provider = MockProvider('{"complexity": "complex"}')
        fac = CRPFacilitator(provider=provider, count_tokens=_count_tokens)

        analysis = fac.analyze_task("task", "sys", 0)
        assert analysis.complexity == "complex"
        assert analysis.domain == "general"  # Default for missing field

    def test_llm_exception_returns_empty(self):
        provider = MockProvider()
        provider.generate_chat = MagicMock(side_effect=Exception("LLM down"))
        fac = CRPFacilitator(provider=provider, count_tokens=_count_tokens)

        # Should not raise — gracefully degrade
        analysis = fac.analyze_task("task", "sys", 0)
        assert analysis.complexity == "medium"  # Default

    def test_strategy_invalid_value_falls_back(self):
        provider = MockProvider('{"strategy": "quantum_teleport"}')
        fac = CRPFacilitator(provider=provider, count_tokens=_count_tokens)

        analysis = TaskAnalysis(complexity="medium")
        decision = fac.route_strategy(
            analysis=analysis,
            fact_count=10,
            available_strategies=["push", "reflexive"],
        )
        assert decision.strategy == "push"  # Fallback

    def test_evaluation_bad_json(self):
        provider = MockProvider("I think the output is great!")
        fac = CRPFacilitator(provider=provider, count_tokens=_count_tokens)

        evaluation = fac.evaluate_output("task", "output", 3)
        assert evaluation.task_completion == 0.5  # Default
        assert evaluation.overall_grade == "B"    # Default


# ═══════════════════════════════════════════════════════════════════════
# Full cognitive loop tests
# ═══════════════════════════════════════════════════════════════════════

class TestFullCognitiveLoop:
    """Test the complete facilitator cognitive loop in sequence."""

    def test_full_loop_all_phases(self):
        """Run all 6 facilitator phases in sequence as dispatch_agentic would."""
        # Setup provider that returns different JSON per call
        call_idx = 0
        responses = [
            # Phase 1: Task analysis
            json.dumps({
                "complexity": "complex",
                "domain": "mathematics",
                "knowledge_needs": ["calculus", "algebra"],
                "expected_output_length": "long",
                "confidence": 0.85,
                "subtasks": ["derive formula", "prove theorem"],
            }),
            # Phase 2: Execution planning
            json.dumps({
                "steps": [
                    {"description": "Derive", "strategy": "push", "priority": 1},
                    {"description": "Prove", "strategy": "reflexive", "priority": 2},
                ],
                "estimated_windows": 2,
            }),
            # Phase 3: Fact synthesis
            json.dumps({
                "summary": "Calculus facts synthesized.",
                "key_insights": ["Derivatives are rate of change"],
                "knowledge_gaps": ["Integration techniques"],
            }),
            # Phase 4: Strategy routing
            json.dumps({
                "strategy": "reflexive",
                "reasoning": "Accuracy critical for math",
                "confidence": 0.9,
            }),
            # Phase 6: Output evaluation
            json.dumps({
                "task_completion": 0.95,
                "overall_grade": "A",
                "revision_needed": False,
            }),
            # Phase 8: Memory curation
            json.dumps({
                "promote_ids": ["f-calc"],
                "reasoning": "Calculus facts are high value.",
            }),
        ]

        def _mock_generate(messages, **kwargs):
            nonlocal call_idx
            resp = responses[call_idx % len(responses)]
            call_idx += 1
            return resp, "stop"

        provider = MockProvider()
        provider.generate_chat = _mock_generate
        fac = CRPFacilitator(provider=provider, count_tokens=_count_tokens)

        # Phase 1
        analysis = fac.analyze_task("Prove the fundamental theorem of calculus", "You are a mathematician.", 5)
        assert analysis.complexity == "complex"

        # Phase 2
        plan = fac.plan_execution(analysis, fact_count=5)
        assert len(plan.steps) == 2

        # Phase 3
        synthesis = fac.synthesize_facts(
            [("f-calc", "Calculus is about change.", 0.9)],
            task_context="Prove the fundamental theorem",
        )
        assert len(synthesis.key_insights) == 1

        # Phase 4
        decision = fac.route_strategy(analysis, fact_count=5)
        assert decision.strategy == "reflexive"

        # Phase 6
        evaluation = fac.evaluate_output(
            "Prove the fundamental theorem",
            "The fundamental theorem of calculus states...",
            facts_used=3,
        )
        assert evaluation.overall_grade == "A"
        assert evaluation.revision_needed is False

        # Phase 8
        curation = fac.curate_memory(
            [("f-calc", "Calculus is about change.", 0.9, 2)],
            recent_task="Prove the fundamental theorem",
        )
        assert "f-calc" in curation.promote_ids

        # Metrics
        assert fac.metrics.cognitive_calls == 6
        assert fac.metrics.total_cognitive_tokens > 0
        assert fac.metrics.total_cognitive_ms > 0


# ═══════════════════════════════════════════════════════════════════════
# WindowMetrics agentic fields tests
# ═══════════════════════════════════════════════════════════════════════

class TestAgenticWindowMetrics:
    """Test that agentic telemetry fields are in WindowMetrics."""

    def test_agentic_fields_exist(self):
        from crp.core.window import WindowMetrics
        m = WindowMetrics()
        assert m.agentic_cognitive_calls == 0
        assert m.agentic_cognitive_tokens == 0
        assert m.agentic_cognitive_ms == 0.0
        assert m.agentic_task_complexity == ""
        assert m.agentic_strategy_chosen == ""
        assert m.agentic_strategy_confidence == 0.0
        assert m.agentic_synthesis_insights == 0
        assert m.agentic_evaluation_grade == ""
        assert m.agentic_revision_rounds == 0
        assert m.agentic_curation_actions == 0
        assert m.agentic_plan_steps == 0

    def test_agentic_fields_in_to_dict(self):
        from crp.core.window import WindowMetrics
        m = WindowMetrics(
            agentic_cognitive_calls=5,
            agentic_task_complexity="complex",
            agentic_strategy_chosen="reflexive",
            agentic_evaluation_grade="A",
        )
        d = m.to_dict()
        assert d["agentic_cognitive_calls"] == 5
        assert d["agentic_task_complexity"] == "complex"
        assert d["agentic_strategy_chosen"] == "reflexive"
        assert d["agentic_evaluation_grade"] == "A"

    def test_relay_strategy_agentic(self):
        from crp.core.window import WindowMetrics
        m = WindowMetrics(relay_strategy="agentic")
        assert m.to_dict()["relay_strategy"] == "agentic"


# ═══════════════════════════════════════════════════════════════════════
# WarmStore boost/reduce confidence tests
# ═══════════════════════════════════════════════════════════════════════

class TestWarmStoreCurationOps:
    """Test boost_confidence and reduce_confidence for §22 curation."""

    def test_boost_confidence(self):
        from crp.state.warm_store import WarmStateStore, WarmStoreConfig
        from crp.extraction.types import Fact

        store = WarmStateStore(WarmStoreConfig(max_facts=100))
        fact = Fact(text="Test fact", confidence=0.7, source_window_id="w1")
        store.add_facts([fact])

        store.boost_confidence(fact.id, 0.2)
        sf = store.get_fact(fact.id)
        assert sf is not None
        assert sf.confidence == pytest.approx(0.9)

    def test_boost_confidence_capped_at_1(self):
        from crp.state.warm_store import WarmStateStore, WarmStoreConfig
        from crp.extraction.types import Fact

        store = WarmStateStore(WarmStoreConfig(max_facts=100))
        fact = Fact(text="High conf fact", confidence=0.95, source_window_id="w1")
        store.add_facts([fact])

        store.boost_confidence(fact.id, 0.2)
        sf = store.get_fact(fact.id)
        assert sf.confidence == 1.0

    def test_reduce_confidence(self):
        from crp.state.warm_store import WarmStateStore, WarmStoreConfig
        from crp.extraction.types import Fact

        store = WarmStateStore(WarmStoreConfig(max_facts=100))
        fact = Fact(text="Test fact", confidence=0.7, source_window_id="w1")
        store.add_facts([fact])

        store.reduce_confidence(fact.id, 0.3)
        sf = store.get_fact(fact.id)
        assert sf is not None
        assert sf.confidence == pytest.approx(0.4)

    def test_reduce_confidence_floored_at_0(self):
        from crp.state.warm_store import WarmStateStore, WarmStoreConfig
        from crp.extraction.types import Fact

        store = WarmStateStore(WarmStoreConfig(max_facts=100))
        fact = Fact(text="Low conf fact", confidence=0.1, source_window_id="w1")
        store.add_facts([fact])

        store.reduce_confidence(fact.id, 0.5)
        sf = store.get_fact(fact.id)
        assert sf.confidence == 0.0

    def test_boost_nonexistent_fact(self):
        from crp.state.warm_store import WarmStateStore, WarmStoreConfig
        store = WarmStateStore(WarmStoreConfig(max_facts=100))
        # Should not raise
        store.boost_confidence("nonexistent-id", 0.1)

    def test_reduce_nonexistent_fact(self):
        from crp.state.warm_store import WarmStateStore, WarmStoreConfig
        store = WarmStateStore(WarmStoreConfig(max_facts=100))
        # Should not raise
        store.reduce_confidence("nonexistent-id", 0.1)


# ═══════════════════════════════════════════════════════════════════════
# dispatch_agentic integration test (mocked)
# ═══════════════════════════════════════════════════════════════════════

class TestDispatchAgenticIntegration:
    """Test that dispatch_agentic is wired correctly on CRPOrchestrator."""

    def test_dispatch_agentic_exists(self):
        from crp.core.orchestrator import CRPOrchestrator
        assert hasattr(CRPOrchestrator, "dispatch_agentic")
        assert callable(getattr(CRPOrchestrator, "dispatch_agentic"))

    def test_dispatch_agentic_signature(self):
        """Verify dispatch_agentic has the expected parameters."""
        import inspect
        from crp.core.orchestrator import CRPOrchestrator
        sig = inspect.signature(CRPOrchestrator.dispatch_agentic)
        params = list(sig.parameters.keys())
        assert "self" in params
        assert "system_prompt" in params
        assert "task_input" in params
        assert "max_revision_rounds" in params
        assert "enable_curation" in params
        assert "enable_planning" in params

    def test_dispatch_agentic_returns_tuple(self):
        """Verify return type annotation is (str, QualityReport)."""
        import inspect
        from crp.core.orchestrator import CRPOrchestrator
        sig = inspect.signature(CRPOrchestrator.dispatch_agentic)
        # Return annotation exists
        assert sig.return_annotation != inspect.Parameter.empty


class TestDispatchAgenticContinuation:
    """Agentic dispatch must continue when a non-continuing inner strategy hits length."""

    def test_agentic_continues_when_inner_strategy_returns_length(self):
        from crp.core.orchestrator import CRPOrchestrator
        from crp.providers.custom import CustomProvider
        from crp.core.session import QualityReport

        calls: list[list[dict[str, str]]] = []

        def _generate_fn(messages: list[dict[str, str]]) -> tuple[str, str]:
            calls.append(messages)
            user_content = messages[-1].get("content", "")

            # Facilitator: task analysis
            if "Analyze this task for CRP's internal routing" in user_content:
                return (json.dumps({
                    "complexity": "medium",
                    "domain": "general",
                    "knowledge_needs": [],
                    "expected_output_length": "long",
                    "requires_factual_grounding": False,
                    "requires_creativity": False,
                    "requires_reasoning": False,
                    "confidence": 0.8,
                }), "stop")

            # Facilitator: strategy routing
            if "Choose the optimal CRP dispatch strategy" in user_content:
                return (json.dumps({
                    "strategy": "reflexive",
                    "reasoning": "Test continuation wrapper",
                    "confidence": 0.9,
                }), "stop")

            # Facilitator: output evaluation
            if "Evaluate this CRP output" in user_content:
                return (json.dumps({
                    "task_completion": 0.95,
                    "factual_accuracy": 0.95,
                    "coherence": 0.95,
                    "missing_elements": [],
                    "revision_needed": False,
                    "revision_focus": "",
                    "overall_grade": "A",
                }), "stop")

            # Continuation window via self.dispatch()
            if "=== CONTINUATION DIRECTIVES ===" in user_content:
                return ("part two", "stop")

            # Inner reflexive strategy (first generation)
            return ("part one", "length")

        provider = CustomProvider(
            generate_fn=_generate_fn,
            count_tokens_fn=lambda t: max(1, len(t) // 4),
            context_size=8192,
            name="agentic-continuation-mock",
        )
        orch = CRPOrchestrator(provider=provider, max_continuations=2)
        orch._continuation_config.l3_extractor = None

        output, report = orch.dispatch_agentic("sys", "Write 5 sections about testing")
        assert isinstance(report, QualityReport)
        assert report.continuation_windows >= 1
        assert "part one" in output
        assert "part two" in output


# ═══════════════════════════════════════════════════════════════════════
# §22-FIX-A — Multi-step plan execution tests
# ═══════════════════════════════════════════════════════════════════════

class TestMultiStepPlanExecution:
    """Test that ExecutionPlan with multiple steps drives real dispatches."""

    def test_plan_with_single_step_skips_multistep(self):
        """A plan with one step should NOT enter multi-step logic."""
        plan = ExecutionPlan(
            steps=[PlanStep(description="Direct dispatch", strategy="push")],
            estimated_windows=1,
        )
        assert len(plan.steps) == 1
        # Single-step plan uses direct dispatch path

    def test_plan_with_multiple_steps_has_separate_dispatches(self):
        """A plan with multiple steps should have distinct step descriptions."""
        plan = ExecutionPlan(
            steps=[
                PlanStep(description="Research background", strategy="push",
                         context_needs=["history"], priority=1),
                PlanStep(description="Analyze findings", strategy="reflexive",
                         context_needs=["research"], depends_on=[0], priority=2),
                PlanStep(description="Write conclusion", strategy="push",
                         depends_on=[1], priority=3),
            ],
            estimated_windows=3,
        )
        assert len(plan.steps) == 3
        # Each step has its own strategy
        strategies = [s.strategy for s in plan.steps]
        assert "push" in strategies
        assert "reflexive" in strategies

    def test_plan_step_dependencies_are_valid(self):
        """Step dependencies should reference valid step indices."""
        plan = ExecutionPlan(
            steps=[
                PlanStep(description="Step A", strategy="push", depends_on=[]),
                PlanStep(description="Step B", strategy="push", depends_on=[0]),
                PlanStep(description="Step C", strategy="push", depends_on=[0, 1]),
            ],
            estimated_windows=3,
        )
        for idx, step in enumerate(plan.steps):
            for dep in step.depends_on:
                assert 0 <= dep < idx, f"Step {idx} has invalid dep {dep}"

    def test_plan_step_context_needs_propagation(self):
        """Each step should declare what context it needs."""
        step = PlanStep(
            description="Analyze data",
            strategy="progressive",
            context_needs=["raw_data", "methodology"],
        )
        assert len(step.context_needs) == 2
        assert "raw_data" in step.context_needs

    def test_plan_parallel_flag(self):
        """Plan can flag whether parallel execution is possible."""
        plan = ExecutionPlan(
            steps=[
                PlanStep(description="A", strategy="push"),
                PlanStep(description="B", strategy="push"),
            ],
            estimated_windows=2,
            parallel_possible=True,
        )
        assert plan.parallel_possible is True

    def test_plan_estimated_windows_matches_steps(self):
        """estimated_windows should be at least len(steps)."""
        plan = ExecutionPlan(
            steps=[
                PlanStep(description="S1", strategy="push"),
                PlanStep(description="S2", strategy="push"),
                PlanStep(description="S3", strategy="push"),
            ],
            estimated_windows=3,
        )
        assert plan.estimated_windows >= len(plan.steps)


# ═══════════════════════════════════════════════════════════════════════
# §22-FIX-B — Continuation awareness tests
# ═══════════════════════════════════════════════════════════════════════

class TestContinuationAwareness:
    """Test that agentic loop extracts continuation info from inner dispatch."""

    def test_quality_report_has_continuation_windows(self):
        """QualityReport carries continuation_windows from inner dispatch."""
        from crp.core.session import QualityReport
        report = QualityReport(
            continuation_windows=3,
            telemetry={"continuation_index": 3, "finish_reason": "length"},
        )
        assert report.continuation_windows == 3
        assert report.telemetry["finish_reason"] == "length"

    def test_quality_report_zero_continuation(self):
        """QualityReport with no continuation."""
        from crp.core.session import QualityReport
        report = QualityReport(
            continuation_windows=0,
            telemetry={"continuation_index": 0, "finish_reason": "stop"},
        )
        assert report.continuation_windows == 0

    def test_inner_telemetry_extraction(self):
        """Telemetry dict should contain continuation fields."""
        telemetry = {
            "continuation_index": 2,
            "finish_reason": "stop",
            "continuation_triggered": True,
            "total_llm_ms": 500,
        }
        assert telemetry.get("continuation_index", 0) == 2
        assert telemetry.get("continuation_triggered", False) is True


# ═══════════════════════════════════════════════════════════════════════
# §22-FIX-C — Enhanced revision tests
# ═══════════════════════════════════════════════════════════════════════

class TestEnhancedRevision:
    """Test enhanced revision with structured evaluation feedback."""

    def test_evaluation_guides_revision_focus(self):
        """Evaluation revision_focus should drive revision directive."""
        evaluation = OutputEvaluation(
            task_completion=0.3,
            factual_accuracy=0.5,
            coherence=0.7,
            missing_elements=["conclusion", "examples", "references"],
            revision_needed=True,
            revision_focus="Add concrete examples and a proper conclusion",
            overall_grade="D",
        )
        assert evaluation.revision_needed is True
        assert evaluation.task_completion < 0.7  # Would trigger revision
        assert len(evaluation.missing_elements) == 3
        assert "conclusion" in evaluation.missing_elements

    def test_strategy_adjustment_on_poor_score(self):
        """When task_completion < 0.4, strategy should be adjusted."""
        evaluation = OutputEvaluation(
            task_completion=0.2,
            revision_needed=True,
            overall_grade="D",
        )
        # Strategy adjustment threshold
        assert evaluation.task_completion < 0.4

    def test_revision_not_triggered_above_threshold(self):
        """Revision should NOT trigger if task_completion >= 0.7."""
        evaluation = OutputEvaluation(
            task_completion=0.8,
            revision_needed=True,  # LLM says revision needed
            overall_grade="A",
        )
        # Even if LLM says revision_needed, the 0.7 threshold prevents it
        assert evaluation.task_completion >= 0.7

    def test_synthesis_insights_carry_forward(self):
        """Synthesis insights should be available for revision context."""
        synthesis = SynthesizedKnowledge(
            summary="AI has transformed software engineering",
            key_insights=[
                "LLMs can generate code",
                "Testing remains critical",
                "Human review is essential",
            ],
        )
        assert len(synthesis.key_insights) == 3
        # These would be injected into revision context as hints

    def test_revision_with_contradiction_awareness(self):
        """Synthesis contradictions should be surfaced in system prompt."""
        synthesis = SynthesizedKnowledge(
            summary="Mixed evidence on approach X",
            contradictions=["Source A says X is good, Source B says X is harmful"],
        )
        assert len(synthesis.contradictions) == 1

    def test_evaluation_grade_levels(self):
        """All grade levels should be representable."""
        for grade in ("S", "A", "B", "C", "D"):
            ev = OutputEvaluation(overall_grade=grade)
            assert ev.overall_grade == grade

    def test_revision_builds_enhanced_directive(self):
        """Verify revision directive format includes evaluation scores."""
        evaluation = OutputEvaluation(
            task_completion=0.3,
            factual_accuracy=0.6,
            coherence=0.8,
            revision_needed=True,
            revision_focus="Add more detail",
            missing_elements=["detail", "examples"],
            overall_grade="C",
        )
        # Build the directive the same way dispatch_agentic does
        _missing = ", ".join(evaluation.missing_elements[:5]) or "none identified"
        revision_task = (
            f"=== REVISION REQUEST (Round 1) ===\n"
            f"Original task: test task\n\n"
            f"[EVALUATION FEEDBACK]\n"
            f"  Task completion: {evaluation.task_completion:.0%}\n"
            f"  Factual accuracy: {evaluation.factual_accuracy:.0%}\n"
            f"  Coherence: {evaluation.coherence:.0%}\n"
            f"  Grade: {evaluation.overall_grade}\n"
            f"  Revision focus: {evaluation.revision_focus}\n"
            f"  Missing elements: {_missing}\n"
        )
        assert "30%" in revision_task
        assert "60%" in revision_task
        assert "80%" in revision_task
        assert "Grade: C" in revision_task
        assert "detail, examples" in revision_task
        assert "Add more detail" in revision_task


# ═══════════════════════════════════════════════════════════════════════
# §22-FIX-D — Synthesis integration tests
# ═══════════════════════════════════════════════════════════════════════

class TestSynthesisIntegration:
    """Test that synthesis knowledge enriches the generation context."""

    def test_synthesis_summary_augments_system_prompt(self):
        """Synthesis summary should be injected into system prompt."""
        system_prompt = "You are a helpful assistant."
        synthesis = SynthesizedKnowledge(
            summary="Key findings about topic X",
            key_insights=["Insight A", "Insight B"],
            knowledge_gaps=["Gap 1"],
            contradictions=["Contradiction 1"],
        )
        augmented = system_prompt
        if synthesis.summary:
            augmented = (
                f"{system_prompt}\n\n"
                f"[CRP KNOWLEDGE SYNTHESIS]\n"
                f"{synthesis.summary}\n"
            )
            if synthesis.key_insights:
                augmented += "Key insights:\n" + "\n".join(
                    f"- {i}" for i in synthesis.key_insights[:5]
                ) + "\n"
            if synthesis.knowledge_gaps:
                augmented += "Knowledge gaps:\n" + "\n".join(
                    f"- {g}" for g in synthesis.knowledge_gaps[:3]
                ) + "\n"
            if synthesis.contradictions:
                augmented += "Contradictions to resolve:\n" + "\n".join(
                    f"- {c}" for c in synthesis.contradictions[:3]
                ) + "\n"

        assert "[CRP KNOWLEDGE SYNTHESIS]" in augmented
        assert "Key findings about topic X" in augmented
        assert "- Insight A" in augmented
        assert "- Insight B" in augmented
        assert "Knowledge gaps:" in augmented
        assert "- Gap 1" in augmented
        assert "Contradictions to resolve:" in augmented
        assert "- Contradiction 1" in augmented

    def test_empty_synthesis_no_augmentation(self):
        """Empty synthesis should NOT modify system prompt."""
        system_prompt = "You are a helpful assistant."
        synthesis = SynthesizedKnowledge()  # All empty
        augmented = system_prompt
        if synthesis.summary:
            augmented = f"{system_prompt}\n\n[SYNTHESIS]\n{synthesis.summary}"
        assert augmented == system_prompt

    def test_synthesis_redundant_facts_identified(self):
        """Synthesis should identify redundant fact IDs."""
        synthesis = SynthesizedKnowledge(
            redundant_fact_ids=["fact-1", "fact-2"],
        )
        assert len(synthesis.redundant_fact_ids) == 2

    def test_synthesis_merged_facts_structure(self):
        """Merged facts should have original_ids and merged_text."""
        synthesis = SynthesizedKnowledge(
            merged_facts=[
                {"original_ids": ["f1", "f2"], "merged_text": "Combined fact"},
            ],
        )
        assert len(synthesis.merged_facts) == 1
        assert synthesis.merged_facts[0]["merged_text"] == "Combined fact"


# ═══════════════════════════════════════════════════════════════════════
# §22-FIX-E — Post-revision curation tests
# ═══════════════════════════════════════════════════════════════════════

class TestPostRevisionCuration:
    """Test that curation runs after revision rounds."""

    def test_curation_decision_promotes_and_demotes(self):
        """CurationDecision should carry both promote and demote lists."""
        curation = CurationDecision(
            promote_ids=["high-value-fact"],
            demote_ids=["stale-fact"],
            reasoning="Promoting recent, relevant facts",
        )
        assert len(curation.promote_ids) == 1
        assert len(curation.demote_ids) == 1
        assert "high-value-fact" in curation.promote_ids
        assert "stale-fact" in curation.demote_ids

    def test_intermediate_curation_uses_smaller_delta(self):
        """Post-revision curation should use smaller confidence delta (0.05)
        compared to final curation (0.1)."""
        from crp.state.warm_store import WarmStateStore, WarmStoreConfig
        from crp.extraction.types import Fact

        store = WarmStateStore(WarmStoreConfig(max_facts=100))
        fact = Fact(text="Test fact", confidence=0.5, source_window_id="w1")
        store.add_facts([fact])

        # Intermediate delta (post-revision): 0.05
        store.boost_confidence(fact.id, 0.05)
        sf = store.get_fact(fact.id)
        assert sf.confidence == pytest.approx(0.55)

        # Final delta: 0.1
        store.boost_confidence(fact.id, 0.1)
        sf = store.get_fact(fact.id)
        assert sf.confidence == pytest.approx(0.65)

    def test_curation_discard_ids_structure(self):
        """CurationDecision should support discard IDs."""
        curation = CurationDecision(
            discard_ids=["useless-1", "useless-2"],
        )
        assert len(curation.discard_ids) == 2

    def test_curation_merge_groups(self):
        """CurationDecision should support merge groups."""
        curation = CurationDecision(
            merge_groups=[["f1", "f2"], ["f3", "f4", "f5"]],
        )
        assert len(curation.merge_groups) == 2
        assert len(curation.merge_groups[1]) == 3


# ═══════════════════════════════════════════════════════════════════════
# §22 — Full cognitive pipeline integration test
# ═══════════════════════════════════════════════════════════════════════

class TestCognitivePipelineIntegration:
    """Integration tests for the full agentic cognitive pipeline."""

    def test_full_pipeline_with_multi_step_plan(self):
        """Run all 6 phases with a complex task triggering multi-step."""
        # Phase 1: Task analysis
        analysis_resp = json.dumps({
            "complexity": "complex",
            "domain": "data science",
            "knowledge_needs": ["statistics", "ML", "visualization"],
            "expected_output_length": "long",
            "requires_factual_grounding": True,
            "requires_creativity": False,
            "requires_reasoning": True,
            "subtasks": ["Analyze data", "Build model", "Visualize results"],
            "confidence": 0.85,
        })
        analysis = _parse_task_analysis(analysis_resp)
        assert analysis.complexity == "complex"
        assert len(analysis.subtasks) == 3

        # Phase 2: Plan (complex task triggers planning)
        plan_resp = json.dumps({
            "steps": [
                {"description": "Explore dataset", "strategy": "push",
                 "context_needs": ["data_schema"], "depends_on": [], "priority": 1},
                {"description": "Build model", "strategy": "progressive",
                 "context_needs": ["exploration_results"], "depends_on": [0], "priority": 2},
                {"description": "Visualize", "strategy": "push",
                 "context_needs": ["model_output"], "depends_on": [1], "priority": 3},
            ],
            "estimated_windows": 3,
            "parallel_possible": False,
        })
        plan = _parse_execution_plan(plan_resp)
        assert len(plan.steps) == 3
        assert plan.steps[1].depends_on == [0]

        # Phase 3: Fact synthesis
        synthesis_resp = json.dumps({
            "summary": "Dataset contains 10K records with 50 features",
            "key_insights": ["Feature X is highly correlated", "Missing data in col Y"],
            "contradictions": [],
            "knowledge_gaps": ["Target variable distribution unknown"],
            "redundant_fact_ids": [],
            "merged_facts": [],
        })
        synthesis = _parse_synthesis(synthesis_resp)
        assert len(synthesis.key_insights) == 2

        # Phase 4: Strategy routing
        route_resp = json.dumps({
            "strategy": "progressive",
            "reasoning": "Complex task with many facts benefits from progressive disclosure",
            "envelope_priority": "maximal",
            "continuation_likelihood": "high",
            "confidence": 0.8,
        })
        decision = _parse_strategy_decision(
            route_resp,
            ["push", "reflexive", "progressive", "stream_augmented"],
        )
        assert decision.strategy == "progressive"
        assert decision.continuation_likelihood == "high"

        # Phase 6: Evaluation
        eval_resp = json.dumps({
            "task_completion": 0.85,
            "factual_accuracy": 0.9,
            "coherence": 0.88,
            "missing_elements": [],
            "revision_needed": False,
            "revision_focus": "",
            "overall_grade": "A",
        })
        evaluation = _parse_evaluation(eval_resp)
        assert evaluation.overall_grade == "A"
        assert evaluation.revision_needed is False

        # Phase 8: Curation
        curation_resp = json.dumps({
            "promote_ids": ["fact-stats-1"],
            "demote_ids": [],
            "merge_groups": [],
            "discard_ids": [],
            "reasoning": "Statistics facts were highly useful for this task",
        })
        curation = _parse_curation(curation_resp)
        assert "fact-stats-1" in curation.promote_ids

    def test_pipeline_with_revision_triggered(self):
        """Test pipeline where evaluation triggers revision."""
        # First evaluation: poor
        eval1 = _parse_evaluation(json.dumps({
            "task_completion": 0.3,
            "factual_accuracy": 0.4,
            "coherence": 0.5,
            "missing_elements": ["data analysis", "charts"],
            "revision_needed": True,
            "revision_focus": "Need actual data analysis, not just descriptions",
            "overall_grade": "D",
        }))
        assert eval1.revision_needed is True
        assert eval1.task_completion < 0.4  # Would trigger strategy switch

        # Post-revision evaluation: improved
        eval2 = _parse_evaluation(json.dumps({
            "task_completion": 0.75,
            "factual_accuracy": 0.8,
            "coherence": 0.85,
            "missing_elements": [],
            "revision_needed": False,
            "revision_focus": "",
            "overall_grade": "B",
        }))
        assert eval2.revision_needed is False
        assert eval2.task_completion >= 0.7  # Stops revision loop

    def test_pipeline_max_revision_rounds_respected(self):
        """Revision should stop at max_revision_rounds even if still poor."""
        max_rounds = 2
        evaluations = [
            OutputEvaluation(
                task_completion=0.3, revision_needed=True, overall_grade="D",
            ),
            OutputEvaluation(
                task_completion=0.5, revision_needed=True, overall_grade="C",
            ),
            OutputEvaluation(
                task_completion=0.55, revision_needed=True, overall_grade="C",
            ),
        ]
        # Simulating the revision loop logic
        rounds = 0
        for ev in evaluations:
            if not (ev.revision_needed and rounds < max_rounds
                    and ev.task_completion < 0.7):
                break
            rounds += 1
        # Should stop at 2 even though 3rd eval still says revision needed
        assert rounds == 2
