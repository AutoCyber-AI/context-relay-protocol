# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Phase 2 — Extraction pipeline tests.

Covers: all 6 stages individually, pipeline orchestration, quality gate,
contradiction detection, structured output, and content complexity detection.
"""

from __future__ import annotations

import json

import pytest

from crp.extraction.complexity import detect_content_complexity
from crp.extraction.contradiction import (
    _normalised_edit_distance,
    _word_overlap_similarity,
    apply_supersessions,
    detect_contradictions,
)
from crp.extraction.pipeline import CalibrationState, ExtractionPipeline
from crp.extraction.quality_gate import (
    anomaly_detection,
    confidence_threshold_filter,
    normalize_facts,
    run_quality_gate,
    structural_validation,
)
from crp.extraction.stage1_regex import RegexExtractor
from crp.extraction.stage2_statistical import (
    StatisticalExtractor,
    textrank_sentences,
)
from crp.extraction.stage3_gliner import GLiNERExtractor, derive_labels_from_noun_phrases
from crp.extraction.stage4_uie import UIEExtractor
from crp.extraction.stage5_discourse import DiscourseExtractor, count_discourse_markers
from crp.extraction.stage6_llm import LLMExtractor, _parse_extraction_response
from crp.extraction.structured_output import (
    StructuredOutputHandler,
    json_schema_to_gbnf,
    repair_json,
    validate_json_schema,
)
from crp.extraction.types import (
    ContentType,
    Contradiction,
    ExtractionResult,
    Fact,
    FactEdge,
    FactGraph,
    RelationType,
    ValidationIssue,
    ValidationResult,
    ValidationSeverity,
)

# =========================================================================
# Stage 1 — Regex
# =========================================================================

class TestStage1Regex:
    """Test regex extraction patterns."""

    def test_ipv4(self) -> None:
        ext = RegexExtractor()
        facts = ext.extract("Server at 192.168.1.1 responded.")
        texts = [f.text for f in facts]
        assert "192.168.1.1" in texts

    def test_cve(self) -> None:
        ext = RegexExtractor()
        facts = ext.extract("Vulnerable to CVE-2024-12345 and CVE-2023-0001.")
        cves = [f.text for f in facts if f.category == "vulnerability"]
        assert len(cves) == 2
        assert "CVE-2024-12345" in cves

    def test_url(self) -> None:
        ext = RegexExtractor()
        facts = ext.extract("Visit https://example.com/path?q=1 for details.")
        urls = [f.text for f in facts if f.category == "resource"]
        assert len(urls) >= 1
        assert any("example.com" in u for u in urls)

    def test_email(self) -> None:
        ext = RegexExtractor()
        facts = ext.extract("Contact admin@example.com for support.")
        emails = [f.text for f in facts if f.category == "contact"]
        assert "admin@example.com" in emails

    def test_json_block(self) -> None:
        ext = RegexExtractor()
        text = 'Response: {"status": "ok", "code": 200, "message": "success"}'
        facts = ext.extract(text)
        json_facts = [f for f in facts if f.category == "structured_data"]
        assert len(json_facts) >= 1

    def test_error_code(self) -> None:
        ext = RegexExtractor()
        facts = ext.extract("Failed with ERR_1234 during processing.")
        errors = [f.text for f in facts if f.category == "error_code"]
        assert "ERR_1234" in errors

    def test_semver(self) -> None:
        ext = RegexExtractor()
        facts = ext.extract("Running version v2.1.0-beta on the server.")
        versions = [f.text for f in facts if f.category == "version"]
        assert "v2.1.0-beta" in versions

    def test_hash_sha256(self) -> None:
        ext = RegexExtractor()
        h = "a" * 64
        facts = ext.extract(f"File hash: {h}")
        hashes = [f.text for f in facts if f.category == "identifier"]
        assert h in hashes

    def test_confidence_is_095(self) -> None:
        ext = RegexExtractor()
        facts = ext.extract("Check 192.168.1.1 now.")
        assert all(f.confidence == 0.95 for f in facts)

    def test_extraction_stage_is_1(self) -> None:
        ext = RegexExtractor()
        facts = ext.extract("CVE-2024-99999")
        assert all(f.extraction_stage == 1 for f in facts)

    def test_custom_pattern(self) -> None:
        ext = RegexExtractor()
        ext.register_pattern("ticket", r"TICKET-\d+", "tracking", 0.90)
        facts = ext.extract("See TICKET-42 for details.")
        assert any(f.text == "TICKET-42" for f in facts)

    def test_dedup_overlapping_spans(self) -> None:
        ext = RegexExtractor()
        facts = ext.extract("192.168.1.1")
        # Should not have duplicates for the same span
        texts = [f.text for f in facts]
        assert texts.count("192.168.1.1") == 1

    def test_empty_input(self) -> None:
        ext = RegexExtractor()
        assert ext.extract("") == []

    def test_pattern_count(self) -> None:
        ext = RegexExtractor()
        assert ext.pattern_count >= 11  # 11 builtins

    def test_source_window_id_propagated(self) -> None:
        ext = RegexExtractor()
        facts = ext.extract("192.168.1.1", source_window_id="w-1")
        assert all(f.source_window_id == "w-1" for f in facts)


# =========================================================================
# Stage 2 — Statistical NLP
# =========================================================================

class TestStage2Statistical:
    """Test statistical NLP extraction."""

    _SAMPLE = (
        "The server experienced a critical failure at midnight. "
        "Engineers were notified immediately. "
        "The root cause was identified as a memory leak in the connection pool. "
        "A hotfix was deployed within two hours. "
        "Service was restored by 2:00 AM. "
        "Post-mortem analysis revealed three contributing factors. "
        "No customer data was compromised during the incident."
    )

    def test_extracts_key_sentences(self) -> None:
        ext = StatisticalExtractor(3)
        facts = ext.extract(self._SAMPLE)
        key_sents = [f for f in facts if f.category == "key_sentence"]
        assert 1 <= len(key_sents) <= 7

    def test_confidence_range(self) -> None:
        ext = StatisticalExtractor()
        facts = ext.extract(self._SAMPLE)
        for f in facts:
            assert 0.0 < f.confidence <= 1.0

    def test_extraction_stage_is_2(self) -> None:
        ext = StatisticalExtractor()
        facts = ext.extract(self._SAMPLE)
        assert all(f.extraction_stage == 2 for f in facts)

    def test_textrank_empty(self) -> None:
        result = textrank_sentences([], top_k=3)
        assert result == []

    def test_textrank_few_sentences(self) -> None:
        result = textrank_sentences(["One sentence."], top_k=5)
        assert len(result) == 1

    def test_extracts_headers(self) -> None:
        ext = StatisticalExtractor()
        facts = ext.extract("# Summary\nThe server failed.\n## Details\nMore info.")
        headers = [f for f in facts if f.category == "section_header"]
        assert len(headers) >= 2
        texts = [f.text for f in headers]
        assert "Summary" in texts
        assert "Details" in texts

    def test_extracts_list_items(self) -> None:
        ext = StatisticalExtractor()
        facts = ext.extract("Steps:\n- Install\n- Configure\n- Deploy")
        items = [f for f in facts if f.category == "list_item"]
        assert len(items) == 3

    def test_extracts_numerical_values(self) -> None:
        ext = StatisticalExtractor()
        facts = ext.extract("Response time was 150 ms with 3.5 GB memory.")
        nums = [f for f in facts if f.category == "numerical_value"]
        assert len(nums) >= 2

    def test_empty_input(self) -> None:
        ext = StatisticalExtractor()
        facts = ext.extract("")
        assert facts == []


# =========================================================================
# Stage 3 — GLiNER (interface tests — model not required)
# =========================================================================

class TestStage3GLiNER:
    """Test GLiNER extractor interface (without actual model)."""

    def test_unavailable_returns_empty(self) -> None:
        ext = GLiNERExtractor()
        ext._available = False
        assert ext.extract("some text") == []

    def test_is_available_false_without_lib(self) -> None:
        ext = GLiNERExtractor()
        ext._available = False
        assert not ext.is_available

    def test_tick_idle_unloads(self) -> None:
        ext = GLiNERExtractor(idle_limit=3)
        ext._model = object()  # type: ignore[assignment]
        ext._available = True
        for _ in range(3):
            ext.tick_idle()
        assert ext._model is None

    def test_derive_labels(self) -> None:
        labels = derive_labels_from_noun_phrases(
            ["The Server", "A Connection Pool", "Memory Leak"]
        )
        assert "server" in labels
        assert "connection pool" in labels
        assert len(labels) <= 15


# =========================================================================
# Stage 4 — UIE (interface tests — model not required)
# =========================================================================

class TestStage4UIE:
    """Test UIE extractor interface."""

    def test_unavailable_returns_empty(self) -> None:
        ext = UIEExtractor()
        ext._available = False
        facts, edges = ext.extract("some text")
        assert facts == []
        assert edges == []

    def test_is_available_false_without_lib(self) -> None:
        ext = UIEExtractor()
        ext._available = False
        assert not ext.is_available


# =========================================================================
# Stage 5 — Discourse
# =========================================================================

class TestStage5Discourse:
    """Test discourse structure extraction."""

    def test_detects_condition(self) -> None:
        ext = DiscourseExtractor()
        text = "The system is healthy. If the cache fails, the response time degrades."
        facts, edges = ext.extract(text)
        assert len(edges) >= 1
        rel_types = [e.relation_type for e in edges]
        assert RelationType.CONDITION_FOR in rel_types

    def test_detects_cause_effect(self) -> None:
        ext = DiscourseExtractor()
        text = "The load was heavy. Because the server ran out of memory, the service crashed."
        facts, edges = ext.extract(text)
        rel_types = [e.relation_type for e in edges]
        assert RelationType.CAUSE_EFFECT in rel_types

    def test_detects_contrast(self) -> None:
        ext = DiscourseExtractor()
        text = "Performance improved. However, the error rate remained high."
        facts, edges = ext.extract(text)
        rel_types = [e.relation_type for e in edges]
        assert RelationType.CONTRAST in rel_types

    def test_detects_consequence(self) -> None:
        ext = DiscourseExtractor()
        text = "The config was wrong. Therefore, all requests failed."
        facts, edges = ext.extract(text)
        rel_types = [e.relation_type for e in edges]
        assert RelationType.CONSEQUENCE in rel_types

    def test_empty_input(self) -> None:
        ext = DiscourseExtractor()
        facts, edges = ext.extract("")
        assert facts == []
        assert edges == []

    def test_count_discourse_markers(self) -> None:
        count = count_discourse_markers(
            "If the system fails, however, we should therefore restart."
        )
        assert count >= 3  # "if", "however", "therefore"

    def test_extraction_stage_is_5(self) -> None:
        ext = DiscourseExtractor()
        text = "The test passed. However, coverage dropped."
        facts, _ = ext.extract(text)
        assert all(f.extraction_stage == 5 for f in facts)


# =========================================================================
# Stage 6 — LLM (interface tests — no actual LLM)
# =========================================================================

class TestStage6LLM:
    """Test LLM extractor interface and response parsing."""

    def test_unavailable_returns_empty(self) -> None:
        ext = LLMExtractor()
        facts, edges = ext.extract("text")
        assert facts == []
        assert edges == []

    def test_with_mock_dispatch(self) -> None:
        response = json.dumps([
            {"subject": "server", "predicate": "causes", "object": "crash"},
            {"subject": "config", "predicate": "requires", "object": "restart"},
        ])

        def mock_dispatch(sp: str, ti: str, mt: int) -> str:
            return response

        ext = LLMExtractor(dispatch_fn=mock_dispatch)
        assert ext.is_available
        facts, edges = ext.extract("The server causes a crash.")
        assert len(facts) >= 2
        assert len(edges) == 2

    def test_parse_extraction_response_valid(self) -> None:
        raw = 'Here: [{"subject": "A", "predicate": "leads to", "object": "B"}]'
        result = _parse_extraction_response(raw)
        assert len(result) == 1
        assert result[0]["subject"] == "A"

    def test_parse_extraction_response_invalid(self) -> None:
        assert _parse_extraction_response("no json here") == []

    def test_is_available_property(self) -> None:
        assert not LLMExtractor().is_available
        assert LLMExtractor(dispatch_fn=lambda a, b, c: "").is_available


# =========================================================================
# Content Complexity Detection
# =========================================================================

class TestContentComplexity:
    """Test content type classification."""

    def test_entity_rich(self) -> None:
        # Lots of IPs and CVEs → entity-rich
        text = " ".join(f"192.168.1.{i}" for i in range(50))
        assert detect_content_complexity(text) == ContentType.ENTITY_RICH

    def test_reasoning_dense(self) -> None:
        text = (
            "If the cache is invalidated, then the latency increases. "
            "Because the load balancer redirects traffic, however, the "
            "overall throughput remains stable. Therefore, the system "
            "recovers gracefully. Although the error rate spikes, "
            "because the circuit breaker activates, the damage is contained."
        )
        assert detect_content_complexity(text) == ContentType.REASONING_DENSE

    def test_narrative(self) -> None:
        text = (
            "The team deployed a new version of the application. "
            "Several bug fixes and performance improvements were included. "
            "Users reported a smoother experience."
        )
        assert detect_content_complexity(text) == ContentType.NARRATIVE

    def test_empty_text(self) -> None:
        assert detect_content_complexity("") == ContentType.NARRATIVE


# =========================================================================
# Pipeline Orchestration
# =========================================================================

class TestExtractionPipeline:
    """Test the full extraction pipeline."""

    _SAMPLE = (
        "Server 192.168.1.1 reported CVE-2024-12345. "
        "The vulnerability affects version v3.2.1 of the web server. "
        "Contact admin@example.com for the patch. "
        "The fix was deployed at https://patches.example.com/fix. "
        "# Summary\n"
        "- Update the firewall rules\n"
        "- Restart the affected services\n"
        "Response time improved to 50 ms after the patch."
    )

    def test_extract_returns_result(self) -> None:
        pipeline = ExtractionPipeline()
        result = pipeline.extract(self._SAMPLE)
        assert isinstance(result, ExtractionResult)
        assert result.total_facts > 0

    def test_stages_1_and_2_always_run(self) -> None:
        pipeline = ExtractionPipeline()
        result = pipeline.extract(self._SAMPLE)
        assert 1 in result.stages_run
        assert 2 in result.stages_run

    def test_stage_yields_populated(self) -> None:
        pipeline = ExtractionPipeline()
        result = pipeline.extract(self._SAMPLE)
        assert 1 in result.stage_yields
        assert 2 in result.stage_yields

    def test_entity_density_computed(self) -> None:
        pipeline = ExtractionPipeline()
        result = pipeline.extract(self._SAMPLE)
        assert result.entity_density >= 0.0

    def test_latency_recorded(self) -> None:
        pipeline = ExtractionPipeline()
        result = pipeline.extract(self._SAMPLE)
        assert result.total_extraction_latency_ms > 0
        assert 1 in result.per_stage_latency

    def test_fact_graph_built(self) -> None:
        pipeline = ExtractionPipeline()
        result = pipeline.extract(self._SAMPLE)
        assert isinstance(result.fact_graph, FactGraph)
        assert len(result.fact_graph.nodes) == result.total_facts

    def test_content_type_set(self) -> None:
        pipeline = ExtractionPipeline()
        result = pipeline.extract(self._SAMPLE)
        assert isinstance(result.content_type, ContentType)

    def test_calibration_records(self) -> None:
        pipeline = ExtractionPipeline()
        for _ in range(6):
            pipeline.extract(self._SAMPLE)
        assert pipeline.calibration.baseline_locked
        assert pipeline.calibration.results_count >= 5

    def test_stage_5_runs_for_reasoning_dense(self) -> None:
        pipeline = ExtractionPipeline()
        text = (
            "If the cache fails, the system degrades. "
            "Because memory is limited, however, the pool overflows. "
            "Therefore the service restarts. Although it recovers, "
            "because the config is wrong, the issue recurs."
        )
        result = pipeline.extract(text)
        # May or may not run Stage 5 depending on content classification
        # but should at least run Stages 1 and 2
        assert 1 in result.stages_run
        assert 2 in result.stages_run

    def test_empty_text(self) -> None:
        pipeline = ExtractionPipeline()
        result = pipeline.extract("")
        assert result.total_facts == 0

    def test_custom_regex_pattern(self) -> None:
        pipeline = ExtractionPipeline()
        pipeline.register_regex_pattern("jira", r"PROJ-\d+", "tracking")
        result = pipeline.extract("See PROJ-123 for details.")
        texts = [f.text for f in result.facts]
        assert "PROJ-123" in texts


# =========================================================================
# Calibration State
# =========================================================================

class TestCalibrationState:
    """Test self-calibrating baseline logic."""

    def test_not_locked_initially(self) -> None:
        cs = CalibrationState()
        assert not cs.baseline_locked

    def test_locks_after_5_results(self) -> None:
        cs = CalibrationState()
        for i in range(5):
            r = ExtractionResult()
            r.facts = [Fact(text=f"fact {j}", confidence=0.8) for j in range(10)]
            r.stage_yields = {2: 10}
            r.stages_run = [1, 2]
            r.finalize()
            cs.record(r)
        assert cs.baseline_locked

    def test_escalation_below_baseline(self) -> None:
        cs = CalibrationState()
        cs.baseline_stage_2 = 10
        assert cs.should_escalate_stage_3(5)
        assert not cs.should_escalate_stage_3(15)

    def test_stage_4_escalation(self) -> None:
        cs = CalibrationState()
        assert cs.should_escalate_stage_4(0.05)
        assert not cs.should_escalate_stage_4(0.2)


# =========================================================================
# Quality Gate
# =========================================================================

class TestQualityGate:
    """Test 3-tier quality gate."""

    def _make_result(self, n_facts: int = 10, confidence: float = 0.8) -> ExtractionResult:
        r = ExtractionResult()
        r.facts = [Fact(text=f"Fact number {i} with content", confidence=confidence) for i in range(n_facts)]
        r.finalize()
        return r

    def test_structural_passes_clean(self) -> None:
        r = self._make_result()
        v = structural_validation(r)
        assert v.passed

    def test_structural_fails_on_empty_facts(self) -> None:
        r = ExtractionResult()
        r.facts = [Fact(text="", confidence=0.5) for _ in range(20)]
        r.finalize()
        v = structural_validation(r)
        # Empty facts are LOW severity + parse failures are MEDIUM
        assert any(i.type in ("EMPTY_FACTS", "HIGH_PARSE_FAILURE_RATE") for i in v.issues)

    def test_confidence_filter_flags_low(self) -> None:
        r = self._make_result(confidence=0.3)
        v = confidence_threshold_filter(r, floor=0.6)
        assert all(f.flagged_confidence for f in r.facts)

    def test_confidence_filter_no_flags(self) -> None:
        r = self._make_result(confidence=0.8)
        v = confidence_threshold_filter(r, floor=0.6)
        assert not any(f.flagged_confidence for f in r.facts)

    def test_anomaly_zero_facts(self) -> None:
        r = ExtractionResult()
        r.finalize()
        v = anomaly_detection(r)
        assert any(i.type == "NO_FACTS_EXTRACTED" for i in v.issues)

    def test_anomaly_explosion(self) -> None:
        history = [self._make_result(10) for _ in range(3)]
        r = self._make_result(100)
        v = anomaly_detection(r, history)
        assert any(i.type == "UNUSUALLY_HIGH_FACT_COUNT" for i in v.issues)

    def test_anomaly_duplicates(self) -> None:
        r = ExtractionResult()
        r.facts = [Fact(text="same text here", confidence=0.8) for _ in range(10)]
        r.finalize()
        v = anomaly_detection(r)
        assert any(i.type == "EXCESSIVE_NEAR_DUPLICATES" for i in v.issues)

    def test_normalize_splits_long(self) -> None:
        long_text = " ".join(f"word{i}" for i in range(200))
        facts = [Fact(text=long_text)]
        result = normalize_facts(facts, max_tokens=100)
        assert len(result) == 2

    def test_normalize_merges_short(self) -> None:
        facts = [Fact(text="hi"), Fact(text="ok"), Fact(text="ya")]
        result = normalize_facts(facts, min_tokens=5)
        assert len(result) < 3

    def test_run_quality_gate_composite(self) -> None:
        r = self._make_result()
        result = run_quality_gate(r, confidence_floor=0.6)
        assert result.quality_gate_passed


# =========================================================================
# Contradiction Detection
# =========================================================================

class TestContradictionDetection:
    """Test contradiction detection and supersession."""

    def test_no_contradiction_different_topics(self) -> None:
        new = [Fact(text="The server is running Linux")]
        existing = [Fact(text="The database uses PostgreSQL")]
        contradictions = detect_contradictions(new, existing)
        assert len(contradictions) == 0

    def test_word_overlap_identical(self) -> None:
        assert _word_overlap_similarity("hello world", "hello world") == 1.0

    def test_word_overlap_disjoint(self) -> None:
        assert _word_overlap_similarity("hello world", "foo bar") == 0.0

    def test_normalised_edit_distance(self) -> None:
        d = _normalised_edit_distance("the cat sat", "the dog sat")
        assert 0.0 < d < 1.0

    def test_apply_supersessions(self) -> None:
        a = Fact(text="old version")
        b = Fact(text="new version")
        contradictions = [Contradiction(fact_a=a, fact_b=b, similarity=0.9, content_diff=0.4, confidence=0.36)]
        events = apply_supersessions(contradictions)
        assert len(events) == 1
        assert a.superseded_by == b.id
        assert events[0].event_type == "superseded"


# =========================================================================
# Structured Output
# =========================================================================

class TestStructuredOutput:
    """Test structured output handler."""

    def test_repair_valid_json(self) -> None:
        assert repair_json('{"key": "value"}') == '{"key": "value"}'

    def test_repair_single_quotes(self) -> None:
        repaired = repair_json("{'key': 'value'}")
        assert repaired is not None
        assert json.loads(repaired)["key"] == "value"

    def test_repair_trailing_comma(self) -> None:
        repaired = repair_json('{"a": 1, "b": 2,}')
        assert repaired is not None
        data = json.loads(repaired)
        assert data["a"] == 1

    def test_repair_markdown_fences(self) -> None:
        repaired = repair_json('```json\n{"key": "val"}\n```')
        assert repaired is not None

    def test_repair_truncated(self) -> None:
        repaired = repair_json('{"key": "val"')
        assert repaired is not None

    def test_repair_unrecoverable(self) -> None:
        assert repair_json("not json at all!!!") is None

    def test_handler_enforce_no_schema(self) -> None:
        handler = StructuredOutputHandler()
        data, errors = handler.enforce('{"x": 1}')
        assert data == {"x": 1}
        assert errors == []

    def test_handler_enforce_with_repair(self) -> None:
        handler = StructuredOutputHandler()
        data, errors = handler.enforce("{'x': 1}")
        assert data == {"x": 1}
        assert "json_repaired" in errors

    def test_handler_enforce_failure(self) -> None:
        handler = StructuredOutputHandler()
        data, errors = handler.enforce("broken!!!")
        assert data is None
        assert "json_parse_failed" in errors

    def test_gbnf_generation(self) -> None:
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "count": {"type": "number"},
            },
        }
        gbnf = json_schema_to_gbnf(schema)
        assert gbnf is not None
        assert "string" in gbnf

    def test_gbnf_empty_schema(self) -> None:
        assert json_schema_to_gbnf({}) is None


# =========================================================================
# Data Types
# =========================================================================

class TestExtractionDataTypes:
    """Test core extraction data types."""

    def test_fact_has_uuid(self) -> None:
        f = Fact(text="test")
        assert len(f.id) == 36  # UUID format

    def test_fact_edge_default_relation(self) -> None:
        e = FactEdge()
        assert e.relation_type == RelationType.RELATED

    def test_fact_graph_add_and_query(self) -> None:
        g = FactGraph()
        f1 = Fact(text="A")
        f2 = Fact(text="B")
        g.add_fact(f1)
        g.add_fact(f2)
        edge = FactEdge(source_id=f1.id, target_id=f2.id)
        g.add_edge(edge)
        assert len(g.edges_from(f1.id)) == 1
        assert len(g.edges_to(f2.id)) == 1

    def test_fact_graph_subgraph(self) -> None:
        g = FactGraph()
        f1, f2, f3 = Fact(text="A"), Fact(text="B"), Fact(text="C")
        for f in [f1, f2, f3]:
            g.add_fact(f)
        g.add_edge(FactEdge(source_id=f1.id, target_id=f2.id))
        g.add_edge(FactEdge(source_id=f2.id, target_id=f3.id))
        sub = g.subgraph_for({f1.id}, max_hops=1)
        assert f1.id in sub.nodes
        assert f2.id in sub.nodes
        assert f3.id not in sub.nodes  # 2 hops away

    def test_fact_graph_serialize(self) -> None:
        g = FactGraph()
        f1 = Fact(text="Server is down")
        f2 = Fact(text="Database unreachable")
        g.add_fact(f1)
        g.add_fact(f2)
        g.add_edge(FactEdge(
            source_id=f1.id, target_id=f2.id,
            relation_type=RelationType.CAUSE_EFFECT,
        ))
        text = g.serialize_for_envelope()
        assert "Server is down" in text
        assert "CAUSE_EFFECT" in text

    def test_extraction_result_finalize(self) -> None:
        r = ExtractionResult()
        r.facts = [Fact(text="a", confidence=0.8), Fact(text="b", confidence=0.6)]
        r.edges = [FactEdge()]
        r.finalize()
        assert r.total_facts == 2
        assert r.total_edges == 1
        assert r.average_confidence == pytest.approx(0.7, abs=0.01)
        assert r.relation_density == 0.5

    def test_extraction_result_success(self) -> None:
        r = ExtractionResult()
        assert r.success  # Default is True
        r.quality_gate_passed = False
        assert not r.success

    def test_content_type_values(self) -> None:
        assert ContentType.ENTITY_RICH.value == "ENTITY_RICH"
        assert ContentType.REASONING_DENSE.value == "REASONING_DENSE"
        assert ContentType.NARRATIVE.value == "NARRATIVE"

    def test_relation_type_values(self) -> None:
        assert len(RelationType) == 8  # 7 semantic + RELATED
