# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Phase 5 tests — continuation & stitching."""

from __future__ import annotations

import pytest

from crp.extraction.types import Fact, FactEdge


def _make_fact(text: str = "test fact", **kwargs) -> Fact:
    """Create a test Fact with defaults."""
    import uuid

    defaults = {
        "id": str(uuid.uuid4()),
        "text": text,
        "category": "test",
        "source_window_id": "w0",
        "confidence": 0.9,
        "extraction_stage": 1,
        "created_at": 0.0,
        "metadata": {},
    }
    defaults.update(kwargs)
    return Fact(**defaults)


# ═══════════════════════════════════════════════════════════════════
# 5A: Continuation Trigger
# ═══════════════════════════════════════════════════════════════════


class TestDetectWallHit:
    def test_length_finish_reason(self):
        from crp.continuation.trigger import detect_wall_hit

        assert detect_wall_hit("length") is True
        assert detect_wall_hit("max_tokens") is True

    def test_stop_finish_reason(self):
        from crp.continuation.trigger import detect_wall_hit

        assert detect_wall_hit("stop") is False
        assert detect_wall_hit("end_turn") is False

    def test_none_finish_reason_with_token_ratio(self):
        from crp.continuation.trigger import detect_wall_hit

        assert detect_wall_hit(None, output_tokens=9600, max_output_tokens=10000) is True
        assert detect_wall_hit(None, output_tokens=5000, max_output_tokens=10000) is False

    def test_none_finish_reason_no_tokens(self):
        from crp.continuation.trigger import detect_wall_hit

        assert detect_wall_hit(None) is False


class TestEvaluateContinuation:
    def test_all_conditions_met(self):
        from crp.continuation.trigger import evaluate_continuation

        result = evaluate_continuation(
            finish_reason="length",
            gap_score=0.8,
            info_flow=5.0,
            continuation_count=3,
        )
        assert result.should_continue is True
        assert result.reason == "continue"

    def test_no_wall_hit(self):
        from crp.continuation.trigger import evaluate_continuation

        result = evaluate_continuation(
            finish_reason="stop",
            gap_score=0.8,
            info_flow=5.0,
        )
        # Gap override: model stopped but 80% requirements unfulfilled → continue
        assert result.should_continue is True
        assert result.reason == "gap_override"

    def test_no_wall_hit_low_gap(self):
        """When gap is below threshold, trust the model's stop signal."""
        from crp.continuation.trigger import evaluate_continuation

        result = evaluate_continuation(
            finish_reason="stop",
            gap_score=0.2,
            info_flow=5.0,
        )
        assert result.should_continue is False
        assert result.reason == "no_wall_hit"

    def test_gap_fulfilled(self):
        from crp.continuation.trigger import evaluate_continuation

        result = evaluate_continuation(
            finish_reason="length",
            gap_score=0.0,
            info_flow=5.0,
        )
        assert result.should_continue is False
        assert result.reason == "gap_fulfilled"

    def test_info_flow_dead(self):
        from crp.continuation.trigger import evaluate_continuation

        result = evaluate_continuation(
            finish_reason="length",
            gap_score=0.8,
            info_flow=0.0,
        )
        assert result.should_continue is False
        assert result.reason == "info_flow_dead"

    def test_max_continuations(self):
        from crp.continuation.trigger import TriggerConfig, evaluate_continuation

        result = evaluate_continuation(
            finish_reason="length",
            gap_score=0.8,
            info_flow=5.0,
            continuation_count=50,
            config=TriggerConfig(max_continuations=50),
        )
        assert result.should_continue is False
        assert result.reason == "max_continuations_reached"


# ═══════════════════════════════════════════════════════════════════
# 5B: Gap Analysis
# ═══════════════════════════════════════════════════════════════════


class TestRequirementExtraction:
    def test_structural_l1(self):
        from crp.continuation.gap import clear_requirement_cache, extract_task_requirements

        clear_requirement_cache()
        reqs = extract_task_requirements("List 5 steps to implement a REST API")
        assert len(reqs) > 0
        categories = {r.category for r in reqs}
        assert "list_structure" in categories or "enumerated_items" in categories

    def test_semantic_l2(self):
        from crp.continuation.gap import clear_requirement_cache, extract_task_requirements

        clear_requirement_cache()
        reqs = extract_task_requirements(
            "You must include error handling. You should consider performance."
        )
        assert any(r.level == 2 for r in reqs)
        assert any(r.category == "mandatory" for r in reqs)

    def test_caching(self):
        from crp.continuation.gap import clear_requirement_cache, extract_task_requirements

        clear_requirement_cache()
        r1 = extract_task_requirements("Explain database indexing")
        r2 = extract_task_requirements("Explain database indexing")
        assert r1 is r2  # same object from cache


class TestGapAnalysis:
    def test_full_gap(self):
        from crp.continuation.gap import clear_requirement_cache, gap_analysis

        clear_requirement_cache()
        result = gap_analysis(
            "Explain database indexing and query optimization",
            output_facts=[],
        )
        assert result.gap_score > 0.0
        assert result.fulfilled_count == 0

    def test_partial_fulfillment(self):
        from crp.continuation.gap import clear_requirement_cache, gap_analysis

        clear_requirement_cache()
        facts = [
            _make_fact("Database indexing uses B-tree structures for efficient lookups"),
            _make_fact("Query optimization includes analyzing explain plans"),
        ]
        result = gap_analysis(
            "Explain database indexing and query optimization",
            output_facts=facts,
        )
        assert result.gap_score < 1.0

    def test_complete(self):
        from crp.continuation.gap import Requirement, gap_analysis

        reqs = [Requirement(text="done", level=1, fulfilled=True, fulfillment_score=1.0, weight=1.0)]
        result = gap_analysis("test", output_facts=[], requirements=reqs)
        # Pre-fulfilled requirements
        assert result.total_count == 1


# ═══════════════════════════════════════════════════════════════════
# 5C.1: Information Flow Monitor
# ═══════════════════════════════════════════════════════════════════


class TestInformationFlowMonitor:
    def test_record_and_rate(self):
        from crp.continuation.flow import InformationFlowMonitor

        monitor = InformationFlowMonitor()
        monitor.record("w1", facts_produced=10, tokens_consumed=1000)
        assert monitor.current_rate() == 10.0  # 10 facts per 1000 tokens
        assert monitor.is_alive() is True

    def test_rolling_average(self):
        from crp.continuation.flow import InformationFlowMonitor

        monitor = InformationFlowMonitor(rolling_window=3)
        monitor.record("w1", facts_produced=10, tokens_consumed=1000)
        monitor.record("w2", facts_produced=5, tokens_consumed=1000)
        monitor.record("w3", facts_produced=0, tokens_consumed=1000)
        avg = monitor.rolling_average()
        assert 4.0 < avg < 6.0  # ~5.0

    def test_trend(self):
        from crp.continuation.flow import InformationFlowMonitor

        monitor = InformationFlowMonitor(rolling_window=3)
        monitor.record("w1", facts_produced=10, tokens_consumed=1000)
        monitor.record("w2", facts_produced=5, tokens_consumed=1000)
        monitor.record("w3", facts_produced=1, tokens_consumed=1000)
        assert monitor.trend() < 0  # decreasing

    def test_dead_flow(self):
        from crp.continuation.flow import InformationFlowMonitor

        monitor = InformationFlowMonitor()
        monitor.record("w1", facts_produced=0, tokens_consumed=1000)
        assert monitor.is_alive() is False

    def test_metrics(self):
        from crp.continuation.flow import InformationFlowMonitor

        monitor = InformationFlowMonitor()
        monitor.record("w1", facts_produced=5, tokens_consumed=500)
        m = monitor.metrics()
        assert m.current_rate == 10.0
        assert m.sample_count == 1
        assert m.is_alive is True


# ═══════════════════════════════════════════════════════════════════
# 5C.1a-c: Generation Quality Monitor
# ═══════════════════════════════════════════════════════════════════


class TestGenerationQualityMonitor:
    def test_basic_scoring(self):
        from crp.continuation.quality_monitor import GenerationQualityMonitor

        monitor = GenerationQualityMonitor()
        score = monitor.score("This is a test. Furthermore, the system works well.", 3)
        assert 0.0 <= score.overall <= 1.0
        assert score.information_density >= 0.0

    def test_novelty_drops(self):
        from crp.continuation.quality_monitor import GenerationQualityMonitor

        monitor = GenerationQualityMonitor()
        text = "The quick brown fox jumps over the lazy dog. " * 20
        s1 = monitor.score(text, 5, "w1")
        assert s1.novelty == 1.0  # first window = all novel

        s2 = monitor.score(text, 5, "w2")
        assert s2.novelty < s1.novelty  # repeated content = less novel

    def test_anomaly_detection(self):
        from crp.continuation.quality_monitor import GenerationQualityMonitor, QualityConfig

        cfg = QualityConfig(anomaly_drop_ratio=0.7)
        monitor = GenerationQualityMonitor(config=cfg)
        # Good windows with high density
        for i in range(5):
            unique = f"Window {i} alpha bravo charlie delta echo {i * 7}. " * 30
            monitor.score(unique, 20, f"w{i}")

        # Terrible window: repeat exact prior content (kills novelty) + 0 facts
        repeated = "Window 0 alpha bravo charlie delta echo 0. " * 30
        s = monitor.score(repeated, 0, "bad")
        # Should be anomalous: 0 density + 0 novelty
        assert s.overall < monitor.rolling_quality() * 0.7 or s.overall < 0.2
        assert monitor.detect_anomaly() is True


# ═══════════════════════════════════════════════════════════════════
# 5C.2-8: Multi-Signal Completion
# ═══════════════════════════════════════════════════════════════════


class TestCompletionDetector:
    def test_in_progress(self):
        from crp.continuation.completion import CompletionDetector

        cd = CompletionDetector()
        result = cd.evaluate(
            "Here is a detailed explanation of the topic. " * 20,
            facts_produced=10,
            tokens_consumed=1000,
        )
        assert result.is_complete is False or result.reason == "in_progress" or result.reason == "grace_period"

    def test_structural_completion_markers(self):
        from crp.continuation.completion import CompletionDetector

        cd = CompletionDetector()
        result = cd.evaluate(
            "# Conclusion\nIn conclusion, this covers all aspects of the topic.\n\n",
            facts_produced=0,
            tokens_consumed=100,
        )
        # Should detect structural completion signals
        structural = [s for s in result.signals if s.signal.value == "structural_completion"]
        assert structural[0].value > 0.0

    def test_content_type_weighting(self):
        from crp.continuation.completion import CompletionDetector

        cd_entity = CompletionDetector(content_type="ENTITY_RICH")
        cd_narr = CompletionDetector(content_type="NARRATIVE")

        text = "A test output with some facts."
        r1 = cd_entity.evaluate(text, 5, 100)
        r2 = cd_narr.evaluate(text, 5, 100)

        # Entity-rich weights fact_flow more heavily
        fact_w_entity = [s for s in r1.signals if s.signal.value == "fact_flow"][0].weight
        fact_w_narr = [s for s in r2.signals if s.signal.value == "fact_flow"][0].weight
        assert fact_w_entity > fact_w_narr


# ═══════════════════════════════════════════════════════════════════
# 5E: Stitch Algorithm
# ═══════════════════════════════════════════════════════════════════


class TestEchoDetection:
    def test_suffix_prefix_overlap(self):
        from crp.continuation.stitch import detect_echo

        prior = "First part of text. This is the overlapping segment here."
        continuation = " the overlapping segment here. And then new content follows."
        echo = detect_echo(prior, continuation)
        assert len(echo) >= 20

    def test_no_echo(self):
        from crp.continuation.stitch import detect_echo

        echo = detect_echo("Completely different text.", "Totally new content here.")
        assert echo == ""

    def test_lcs_echo(self):
        from crp.continuation.stitch import StitchConfig, detect_echo

        prior = "A" * 100 + "ECHO_START this shared content block is repeated ECHO_END" + "B" * 100
        continuation = "ECHO_START this shared content block is repeated ECHO_END" + "C" * 200
        cfg = StitchConfig(echo_window=3000, min_echo_length=20)
        echo = detect_echo(prior, continuation, cfg)
        assert "shared content block" in echo


class TestStitchOutputs:
    def test_basic_stitch(self):
        from crp.continuation.stitch import stitch_outputs

        result = stitch_outputs("First part of text.", "Second part continues here.")
        assert "First part" in result.text
        assert "Second part" in result.text

    def test_echo_removal(self):
        from crp.continuation.stitch import stitch_outputs

        overlap = "This is the exact overlapping content between windows."
        prior = "Start. " + overlap
        continuation = overlap + " More content follows."
        result = stitch_outputs(prior, continuation)
        # Should not have duplicate overlap
        assert result.text.count(overlap) == 1

    def test_empty_prior(self):
        from crp.continuation.stitch import stitch_outputs

        result = stitch_outputs("", "Content here.")
        assert result.text == "Content here."

    def test_empty_continuation(self):
        from crp.continuation.stitch import stitch_outputs

        result = stitch_outputs("Content here.", "")
        assert result.text == "Content here."

    def test_validation_warnings(self):
        from crp.continuation.stitch import stitch_outputs

        result = stitch_outputs("Open bracket (here", "and close bracket) done.")
        # Brackets should be balanced in final output
        assert isinstance(result.validation_warnings, list)


class TestStitchMany:
    def test_n_way_stitch(self):
        from crp.continuation.stitch import stitch_many

        # Completely distinct outputs with zero shared substrings
        outputs = [
            "Alpha canary zebra quantum photon stellar nebula horizon.",
            "Bravo igloo mercury crimson violet sapphire emerald compass.",
            "Charlie oxygen titanium platinum rhodium iridium osmium radar.",
            "Delta epsilon zeta theta iota kappa lambda mu sigma.",
            "Echo foxtrot golf hotel juliet kilo lima november oscar.",
        ]
        result = stitch_many(outputs)
        assert "Alpha" in result.text
        assert "oscar" in result.text

    def test_empty_list(self):
        from crp.continuation.stitch import stitch_many

        result = stitch_many([])
        assert result.text == ""


# ═══════════════════════════════════════════════════════════════════
# 5F.1-2: Voice Profile
# ═══════════════════════════════════════════════════════════════════


class TestVoiceProfile:
    def test_extract_formal(self):
        from crp.continuation.voice import extract_voice_profile

        # Use formal markers that appear as standalone words after split()
        text = (
            "The implementation therefore demonstrates significant advantages herein. "
            "The system architecture consequently provides considerable benefits accordingly. "
            "The analytical framework moreover yields substantive improvements furthermore. "
            "This notwithstanding the constraints whereby the design was hitherto limited."
        )
        profile = extract_voice_profile(text)
        assert profile.tone in ("formal", "technical")
        assert profile.avg_sentence_length > 0

    def test_extract_casual(self):
        from crp.continuation.voice import extract_voice_profile

        text = (
            "Okay so basically this is pretty cool stuff. "
            "Yeah the thing actually works awesome. "
            "Gonna try it out and see what happens."
        )
        profile = extract_voice_profile(text)
        assert profile.tone == "casual"

    def test_serialization(self):
        from crp.continuation.voice import VoiceProfile

        vp = VoiceProfile(
            tone="formal",
            avg_sentence_length=15.2,
            vocabulary_level="advanced",
            person="third",
            active_voice_ratio=0.7,
            key_terminology=["API", "REST"],
        )
        d = vp.to_dict()
        vp2 = VoiceProfile.from_dict(d)
        assert vp2.tone == "formal"
        assert vp2.key_terminology == ["API", "REST"]


# ═══════════════════════════════════════════════════════════════════
# 5F.3: Document Map
# ═══════════════════════════════════════════════════════════════════


class TestDocumentMap:
    def test_heading_extraction(self):
        from crp.continuation.document_map import DocumentMap

        dm = DocumentMap()
        text = "# Introduction\nSome content.\n## Methods\nMore content."
        new = dm.update(text, "w1")
        assert len(new) == 2
        assert new[0].text == "Introduction"
        assert new[1].text == "Methods"
        assert dm.current_section == "Methods"

    def test_toc_generation(self):
        from crp.continuation.document_map import DocumentMap

        dm = DocumentMap()
        dm.update("# Title\nContent.\n## Section 1\nContent.", "w1")
        dm.update("## Section 2\nMore content.\n### Subsection\nDetails.", "w2")
        toc = dm.get_toc()
        assert "Title" in toc
        assert "Section 1" in toc
        assert "Section 2" in toc

    def test_progress(self):
        from crp.continuation.document_map import DocumentMap

        dm = DocumentMap()
        dm.total_sections_expected = 4
        dm.update("# Section 1\ntext.\n# Section 2\ntext.", "w1")
        assert dm.progress() == 0.5

    def test_missing_sections(self):
        from crp.continuation.document_map import DocumentMap

        dm = DocumentMap()
        dm.update("# Introduction\ntext.", "w1")
        missing = dm.missing_sections(["Introduction", "Methods", "Results"])
        assert "Methods" in missing
        assert "Results" in missing
        assert "Introduction" not in missing

    def test_serialization(self):
        from crp.continuation.document_map import DocumentMap

        dm = DocumentMap()
        dm.update("# Title\nContent.", "w1")
        d = dm.to_dict()
        dm2 = DocumentMap.from_dict(d)
        assert len(dm2.headings) == 1
        assert dm2.headings[0].text == "Title"


# ═══════════════════════════════════════════════════════════════════
# 5F.4-5: Chain Degradation
# ═══════════════════════════════════════════════════════════════════


class TestChainDegradation:
    def test_no_degradation(self):
        from crp.continuation.degradation import ChainDegradation

        cd = ChainDegradation()
        m = cd.record("w1", facts_expected=10, facts_produced=10, quality_score=1.0)
        assert m.d_i == 0.0
        assert cd.chain_degradation == 0.0

    def test_cumulative_formula(self):
        from crp.continuation.degradation import ChainDegradation

        cd = ChainDegradation()
        cd.record("w1", facts_expected=10, facts_produced=8, quality_score=0.9)
        cd.record("w2", facts_expected=10, facts_produced=7, quality_score=0.8)

        # d_chain(n) = 1 - ∏(1 - d_i)
        assert 0.0 < cd.chain_degradation < 1.0
        assert cd.window_count == 2

    def test_should_reground(self):
        from crp.continuation.degradation import ChainDegradation

        cd = ChainDegradation(reground_interval=3)
        for i in range(3):
            cd.record(f"w{i}", facts_expected=10, facts_produced=8, quality_score=0.9)
        assert cd.should_reground() is True

    def test_reground(self):
        from crp.continuation.degradation import ChainDegradation

        cd = ChainDegradation()
        cd.record("w1", facts_expected=5, facts_produced=5, quality_score=1.0)

        current = [_make_fact("Database uses B-tree indexing for fast queries")]
        regrounded = [_make_fact("Database uses B-tree indexing for efficient queries")]

        result = cd.reground(current, regrounded)
        assert result.reconciled >= 0
        assert 0.0 <= result.drift_score <= 1.0


# ═══════════════════════════════════════════════════════════════════
# 5D + 5G: Continuation Manager
# ═══════════════════════════════════════════════════════════════════


class TestContinuationManager:
    def test_build_envelope(self):
        from crp.continuation.gap import GapResult, Requirement
        from crp.continuation.manager import ContinuationManager

        mgr = ContinuationManager()
        gap = GapResult(
            requirements=[],
            gap_score=0.5,
            fulfilled_count=1,
            total_count=2,
            unfulfilled=[Requirement(text="Missing section B", level=1)],
        )
        envelope = mgr.build_continuation_envelope(
            "Write a report",
            gap_result=gap,
            structural_state={"current_section": "Section A", "list_position": 3},
            last_output="This is the last paragraph of content. It has style.",
        )
        assert "STYLE ANCHOR" in envelope
        assert "REMAINING REQUIREMENTS" in envelope
        assert "STRUCTURAL POSITION" in envelope
        assert "CONTINUATION" in envelope

    def test_process_window_first(self):
        from crp.continuation.manager import ContinuationManager

        mgr = ContinuationManager()
        facts = [_make_fact("Fact one"), _make_fact("Fact two")]
        state = mgr.process_window(
            task_intent="Explain databases",
            output="Databases are systems for storing data. " * 20,
            finish_reason="length",
            output_tokens=1000,
            facts=facts,
            window_id="w1",
        )
        assert state.window_count == 1
        assert state.voice_profile is not None

    def test_termination_gap_fulfilled(self):
        from crp.continuation.gap import clear_requirement_cache
        from crp.continuation.manager import ContinuationManager

        clear_requirement_cache()
        mgr = ContinuationManager()
        # Produce facts matching the task requirements
        facts = [
            _make_fact("Explain database indexing comprehensively"),
            _make_fact("Database indexing uses B-trees and hash indexes"),
        ]
        state = mgr.process_window(
            task_intent="Explain database indexing",
            output="Database indexing uses B-trees and hash indexes. " * 30,
            finish_reason="stop",
            output_tokens=500,
            facts=facts,
            window_id="w1",
        )
        # With stop finish_reason, trigger should say no_wall_hit → finished
        assert state.finished is True

    def test_voice_profile_first_window_only(self):
        from crp.continuation.manager import ContinuationManager

        mgr = ContinuationManager()
        facts = [_make_fact("fact")]
        mgr.process_window("task", "First window output text.", "length", 100, facts, "w1")
        v1 = mgr.voice_profile

        mgr.process_window("task", "Second window has different style.", "length", 100, facts, "w2")
        v2 = mgr.voice_profile

        assert v1 is v2  # voice profile extracted only from first window

    def test_document_map_updates(self):
        from crp.continuation.manager import ContinuationManager

        mgr = ContinuationManager()
        facts = [_make_fact("fact")]
        mgr.process_window(
            "task",
            "# Introduction\nContent here.\n## Methods\nMore content.",
            "length", 100, facts, "w1",
        )
        assert len(mgr.document_map.headings) == 2

    def test_stitch_across_windows(self):
        from crp.continuation.manager import ContinuationManager

        mgr = ContinuationManager()
        facts = [_make_fact("fact")]
        mgr.process_window("task", "First window content.", "length", 100, facts, "w1")
        mgr.process_window("task", "Second window content.", "length", 100, facts, "w2")
        assert "First window" in mgr.state.stitched_output
        assert "Second window" in mgr.state.stitched_output

    def test_reset(self):
        from crp.continuation.manager import ContinuationManager

        mgr = ContinuationManager()
        facts = [_make_fact("fact")]
        mgr.process_window("task", "Output.", "length", 100, facts, "w1")
        mgr.reset()
        assert mgr.state.window_count == 0
        assert mgr.voice_profile is None

    def test_degradation_tracking(self):
        from crp.continuation.manager import ContinuationManager

        mgr = ContinuationManager()
        for i in range(5):
            facts = [_make_fact(f"fact {i}")]
            mgr.process_window("task", f"Window {i} output. " * 20, "length", 500, facts, f"w{i}")
        assert mgr.degradation.window_count == 5
        assert isinstance(mgr.state.chain_degradation, float)


# ═══════════════════════════════════════════════════════════════════
# Integration: Full continuation package import
# ═══════════════════════════════════════════════════════════════════


class TestContinuationImports:
    def test_all_exports(self):
        from crp.continuation import (
            ChainDegradation,
            CompletionDetector,
            ContinuationConfig,
            ContinuationManager,
            ContinuationState,
            DocumentMap,
            GapResult,
            GenerationQualityMonitor,
            InformationFlowMonitor,
            Requirement,
            StitchResult,
            TriggerConfig,
            TriggerResult,
            VoiceProfile,
            detect_echo,
            detect_wall_hit,
            evaluate_continuation,
            extract_task_requirements,
            extract_voice_profile,
            gap_analysis,
            stitch_many,
            stitch_outputs,
        )
        assert all([
            ChainDegradation, CompletionDetector, ContinuationConfig,
            ContinuationManager, ContinuationState, DocumentMap,
            GapResult, GenerationQualityMonitor, InformationFlowMonitor,
            Requirement, StitchResult, TriggerConfig, TriggerResult,
            VoiceProfile, detect_echo, detect_wall_hit, evaluate_continuation,
            extract_task_requirements, extract_voice_profile, gap_analysis,
            stitch_many, stitch_outputs,
        ])
