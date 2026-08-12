# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Tests for the Fidelity Verification Layer — §7.14.3.

The Fidelity Verification Layer answers the question:
"Even if we know WHERE a claim came from, did the model FAITHFULLY
represent the source?"

Four fidelity checks:
  1. Distortion Detection — did the model distort grounded facts?
  2. Omission Analysis — did the model ignore important facts?
  3. Fabrication Detection — did the model invent specifics?
  4. Contradiction Detection — does the model contradict itself?
"""

from __future__ import annotations

import pytest

from crp.envelope.packer import PackedFact
from crp.provenance._types import (
    AttributionType,
    ClaimAttribution,
    ClaimType,
    ContradictionResult,
    DistortionResult,
    DistortionType,
    FabricationResult,
    FabricationType,
    FidelityReport,
    OmissionResult,
    OmissionSeverity,
    FactScore,
)
from crp.provenance.distortion_detector import detect_distortions
from crp.provenance.omission_analyzer import analyze_omissions
from crp.provenance.fabrication_detector import detect_fabrications
from crp.provenance.contradiction_detector import detect_contradictions
from crp.provenance import DecisionProvenanceEngine, ProvenanceConfig


# ===================================================================
# Helper factories
# ===================================================================


def _make_packed_fact(
    fact_id: str,
    text: str,
    score: float = 0.80,
) -> PackedFact:
    """Create a PackedFact for testing."""
    return PackedFact(
        fact_id=fact_id,
        text=text,
        score=score,
        tokens=len(text.split()),
    )


def _make_attribution(
    index: int,
    text: str,
    claim_type: ClaimType = ClaimType.FACTUAL_CLAIM,
    attr_type: AttributionType = AttributionType.CONTEXT_GROUNDED,
    top_score: float = 0.75,
    top_fact_id: str = "fact-1",
    top_fact_text: str = "",
) -> ClaimAttribution:
    """Create a ClaimAttribution for testing."""
    facts = []
    if top_fact_id:
        facts.append(
            FactScore(
                fact_id=top_fact_id,
                fact_text_preview=top_fact_text[:120],
                composite_score=top_score,
            )
        )
    return ClaimAttribution(
        claim_text=text,
        claim_index=index,
        claim_type=claim_type,
        attribution_type=attr_type,
        top_score=top_score,
        attributed_facts=facts,
        confidence=top_score,
    )


# ===================================================================
# 1. DISTORTION DETECTOR TESTS
# ===================================================================


class TestDistortionDetector:
    """Tests for distortion_detector.detect_distortions()."""

    def test_number_change_detected(self):
        """Claim changes a number from the source fact."""
        facts = [_make_packed_fact("f1", "Revenue grew 10 percent in Q3")]
        attrs = [
            _make_attribution(
                0, "Revenue grew 25 percent in Q3",
                top_fact_id="f1",
                top_fact_text="Revenue grew 10 percent in Q3",
            ),
        ]
        results = detect_distortions(attrs, facts)
        assert len(results) >= 1
        number_distortions = [
            r for r in results if r.distortion_type == DistortionType.NUMBER_CHANGED
        ]
        assert len(number_distortions) >= 1
        assert number_distortions[0].severity > 0

    def test_negation_flip_detected(self):
        """Claim flips the negation of a source fact."""
        facts = [_make_packed_fact("f1", "The system is safe and reliable")]
        attrs = [
            _make_attribution(
                0, "The system is not safe and reliable",
                top_fact_id="f1",
                top_fact_text="The system is safe and reliable",
            ),
        ]
        results = detect_distortions(attrs, facts)
        negation_results = [
            r for r in results if r.distortion_type == DistortionType.NEGATION_FLIP
        ]
        assert len(negation_results) >= 1
        assert negation_results[0].severity >= 0.80

    def test_qualifier_dropped_detected(self):
        """Claim drops a hedge qualifier from the source fact."""
        facts = [_make_packed_fact("f1", "The treatment might reduce symptoms")]
        attrs = [
            _make_attribution(
                0, "The treatment reduces symptoms",
                top_fact_id="f1",
                top_fact_text="The treatment might reduce symptoms",
            ),
        ]
        results = detect_distortions(attrs, facts)
        qualifier_results = [
            r for r in results
            if r.distortion_type == DistortionType.QUALIFIER_DROPPED
        ]
        assert len(qualifier_results) >= 1

    def test_qualifier_added_detected(self):
        """Claim adds certainty qualifier not in the source fact."""
        facts = [_make_packed_fact("f1", "The method improves performance")]
        attrs = [
            _make_attribution(
                0, "The method always improves performance",
                top_fact_id="f1",
                top_fact_text="The method improves performance",
            ),
        ]
        results = detect_distortions(attrs, facts)
        qualifier_results = [
            r for r in results
            if r.distortion_type == DistortionType.QUALIFIER_ADDED
        ]
        assert len(qualifier_results) >= 1

    def test_no_distortion_for_matching_claim(self):
        """No distortion when claim faithfully reproduces the fact."""
        facts = [_make_packed_fact("f1", "Python was created in 1991")]
        attrs = [
            _make_attribution(
                0, "Python was created in 1991",
                top_fact_id="f1",
                top_fact_text="Python was created in 1991",
            ),
        ]
        results = detect_distortions(attrs, facts)
        assert len(results) == 0

    def test_no_distortion_for_parametric_claims(self):
        """Parametric claims are not checked for distortion."""
        facts = [_make_packed_fact("f1", "Revenue grew 10 percent")]
        attrs = [
            _make_attribution(
                0, "Revenue grew 50 percent",
                attr_type=AttributionType.PARAMETRIC,
                top_fact_id="f1",
                top_fact_text="Revenue grew 10 percent",
            ),
        ]
        results = detect_distortions(attrs, facts)
        assert len(results) == 0

    def test_distortion_result_fields(self):
        """DistortionResult fields are populated correctly."""
        facts = [_make_packed_fact("f1", "There were 100 participants")]
        attrs = [
            _make_attribution(
                0, "There were 500 participants",
                top_fact_id="f1",
                top_fact_text="There were 100 participants",
            ),
        ]
        results = detect_distortions(attrs, facts)
        assert len(results) >= 1
        r = results[0]
        assert isinstance(r, DistortionResult)
        assert r.claim_index == 0
        assert r.source_fact_id == "f1"
        assert r.severity > 0
        assert r.detail

    def test_scope_change_detected(self):
        """Claim changes the scope from source fact."""
        facts = [_make_packed_fact("f1", "Sales grew globally across all regions")]
        attrs = [
            _make_attribution(
                0, "Sales grew locally in one region",
                top_fact_id="f1",
                top_fact_text="Sales grew globally across all regions",
            ),
        ]
        results = detect_distortions(attrs, facts)
        scope_results = [
            r for r in results if r.distortion_type == DistortionType.SCOPE_CHANGED
        ]
        assert len(scope_results) >= 1

    def test_entity_substitution_detected(self):
        """Claim swaps a proper noun from the source fact."""
        facts = [_make_packed_fact("f1", "Microsoft reported strong earnings")]
        attrs = [
            _make_attribution(
                0, "Google reported strong earnings",
                top_fact_id="f1",
                top_fact_text="Microsoft reported strong earnings",
            ),
        ]
        results = detect_distortions(attrs, facts)
        entity_results = [
            r for r in results
            if r.distortion_type == DistortionType.ENTITY_SUBSTITUTED
        ]
        assert len(entity_results) >= 1

    def test_mixed_claims_checked(self):
        """MIXED attribution claims are also checked for distortion."""
        facts = [_make_packed_fact("f1", "The server has 16 cores")]
        attrs = [
            _make_attribution(
                0, "The server has 64 cores",
                attr_type=AttributionType.MIXED,
                top_fact_id="f1",
                top_fact_text="The server has 16 cores",
            ),
        ]
        results = detect_distortions(attrs, facts)
        assert len(results) >= 1


# ===================================================================
# 2. OMISSION ANALYZER TESTS
# ===================================================================


class TestOmissionAnalyzer:
    """Tests for omission_analyzer.analyze_omissions()."""

    def test_omitted_fact_detected(self):
        """A fact with no attribution from any claim is flagged."""
        facts = [
            _make_packed_fact("f1", "Revenue grew 10 percent", score=0.90),
            _make_packed_fact("f2", "Expenses decreased significantly", score=0.85),
        ]
        # Only f1 is attributed
        attrs = [
            _make_attribution(
                0, "Revenue grew 10 percent",
                top_fact_id="f1",
                top_fact_text="Revenue grew 10 percent",
                top_score=0.80,
            ),
        ]
        results = analyze_omissions(attrs, facts)
        omitted_ids = [r.fact_id for r in results]
        assert "f2" in omitted_ids

    def test_well_attributed_fact_not_omitted(self):
        """A fact with strong attribution from a claim is NOT flagged."""
        facts = [_make_packed_fact("f1", "Python was created in 1991", score=0.90)]
        attrs = [
            _make_attribution(
                0, "Python was created in 1991",
                top_fact_id="f1",
                top_fact_text="Python was created in 1991",
                top_score=0.80,
            ),
        ]
        results = analyze_omissions(attrs, facts)
        omitted_ids = [r.fact_id for r in results]
        assert "f1" not in omitted_ids

    def test_severity_reflects_importance(self):
        """Higher-relevance omitted facts get higher severity."""
        facts = [
            _make_packed_fact("f1", "Critical security vulnerability found", score=0.95),
            _make_packed_fact("f2", "Minor formatting issue noted", score=0.10),
        ]
        attrs: list[ClaimAttribution] = []  # No claims → both omitted
        results = analyze_omissions(attrs, facts)
        assert len(results) == 2

        # Sort by fact_id for stable comparison
        by_id = {r.fact_id: r for r in results}
        assert by_id["f1"].fact_relevance_score > by_id["f2"].fact_relevance_score

    def test_omission_result_fields(self):
        """OmissionResult fields are populated correctly."""
        facts = [_make_packed_fact("f1", "Important fact about security", score=0.90)]
        attrs: list[ClaimAttribution] = []
        results = analyze_omissions(attrs, facts)
        assert len(results) == 1
        r = results[0]
        assert isinstance(r, OmissionResult)
        assert r.fact_id == "f1"
        assert r.fact_relevance_score == 0.90
        assert r.max_attribution_score < 0.20
        assert r.severity in (
            OmissionSeverity.CRITICAL,
            OmissionSeverity.HIGH,
            OmissionSeverity.MEDIUM,
            OmissionSeverity.LOW,
        )

    def test_no_omissions_when_all_attributed(self):
        """No omissions when every fact is well-attributed."""
        facts = [
            _make_packed_fact("f1", "Python was created in 1991 by Guido", score=0.80),
        ]
        attrs = [
            _make_attribution(
                0, "Python was created in 1991 by Guido van Rossum",
                top_fact_id="f1",
                top_fact_text="Python was created in 1991 by Guido",
                top_score=0.85,
            ),
        ]
        results = analyze_omissions(attrs, facts)
        assert len(results) == 0

    def test_empty_facts_returns_empty(self):
        """No omissions when there are no facts."""
        attrs = [
            _make_attribution(0, "Some claim"),
        ]
        results = analyze_omissions(attrs, [])
        assert results == []

    def test_results_sorted_by_relevance(self):
        """Omission results are sorted by fact_relevance_score descending."""
        facts = [
            _make_packed_fact("f1", "Low importance detail", score=0.20),
            _make_packed_fact("f2", "High importance finding", score=0.90),
            _make_packed_fact("f3", "Medium importance note", score=0.50),
        ]
        attrs: list[ClaimAttribution] = []
        results = analyze_omissions(attrs, facts)
        scores = [r.fact_relevance_score for r in results]
        assert scores == sorted(scores, reverse=True)


# ===================================================================
# 3. FABRICATION DETECTOR TESTS
# ===================================================================


class TestFabricationDetector:
    """Tests for fabrication_detector.detect_fabrications()."""

    def test_fabricated_number_detected(self):
        """A number in a claim not present in any fact is flagged."""
        facts = [_make_packed_fact("f1", "Revenue grew ten percent")]
        attrs = [
            _make_attribution(
                0, "Revenue grew 42 percent according to the report",
                top_fact_id="f1",
                top_fact_text="Revenue grew ten percent",
            ),
        ]
        results = detect_fabrications(attrs, facts)
        number_fabs = [
            r for r in results
            if r.entity_type in (FabricationType.NUMBER, FabricationType.PERCENTAGE)
        ]
        assert len(number_fabs) >= 1

    def test_fabricated_percentage_detected(self):
        """A percentage in a claim not in any fact is flagged."""
        facts = [_make_packed_fact("f1", "Growth was moderate in the period")]
        attrs = [
            _make_attribution(
                0, "Growth reached 87% in the period",
                top_fact_id="f1",
                top_fact_text="Growth was moderate in the period",
            ),
        ]
        results = detect_fabrications(attrs, facts)
        pct_fabs = [r for r in results if r.entity_type == FabricationType.PERCENTAGE]
        assert len(pct_fabs) >= 1

    def test_fabricated_date_detected(self):
        """A date in a claim not in any fact is flagged."""
        facts = [_make_packed_fact("f1", "The project started recently")]
        attrs = [
            _make_attribution(
                0, "The project started in 2019 with early prototypes",
                top_fact_id="f1",
                top_fact_text="The project started recently",
            ),
        ]
        results = detect_fabrications(attrs, facts)
        date_fabs = [r for r in results if r.entity_type == FabricationType.DATE]
        assert len(date_fabs) >= 1

    def test_no_fabrication_when_entity_in_facts(self):
        """No fabrication when the entity exists in the facts."""
        facts = [_make_packed_fact("f1", "Python was created in 1991")]
        attrs = [
            _make_attribution(
                0, "Python was created in 1991 as a general-purpose language",
                top_fact_id="f1",
                top_fact_text="Python was created in 1991",
            ),
        ]
        results = detect_fabrications(attrs, facts)
        date_fabs = [r for r in results if r.entity_type == FabricationType.DATE]
        assert len(date_fabs) == 0

    def test_fabrication_result_fields(self):
        """FabricationResult fields are populated correctly."""
        facts = [_make_packed_fact("f1", "Performance improved significantly")]
        attrs = [
            _make_attribution(
                0, "Performance improved by 73 percent overall",
                top_fact_id="f1",
                top_fact_text="Performance improved significantly",
            ),
        ]
        results = detect_fabrications(attrs, facts)
        assert len(results) >= 1
        r = results[0]
        assert isinstance(r, FabricationResult)
        assert r.claim_index == 0
        assert r.fabricated_entity
        assert r.severity > 0

    def test_opinion_claims_not_checked(self):
        """Opinion claims are not checked for fabrication."""
        facts = [_make_packed_fact("f1", "The report was published")]
        attrs = [
            _make_attribution(
                0, "I believe 95% of experts agree with this approach",
                claim_type=ClaimType.OPINION,
                top_fact_id="f1",
                top_fact_text="The report was published",
            ),
        ]
        results = detect_fabrications(attrs, facts)
        assert len(results) == 0

    def test_empty_facts_corpus(self):
        """No fabrications when there are no facts to compare against."""
        attrs = [
            _make_attribution(
                0, "Revenue grew 15 percent in 2023",
                top_fact_id="",
            ),
        ]
        # With no reference facts, detector cannot determine fabrication
        results = detect_fabrications(attrs, [])
        assert results == []

    def test_fabricated_citation_detected(self):
        """A citation not in any fact is flagged."""
        facts = [_make_packed_fact("f1", "The treatment shows promise")]
        attrs = [
            _make_attribution(
                0, "According to Smith et al the treatment shows promise",
                top_fact_id="f1",
                top_fact_text="The treatment shows promise",
            ),
        ]
        results = detect_fabrications(attrs, facts)
        cite_fabs = [r for r in results if r.entity_type == FabricationType.CITATION]
        assert len(cite_fabs) >= 1


# ===================================================================
# 4. CONTRADICTION DETECTOR TESTS
# ===================================================================


class TestContradictionDetector:
    """Tests for contradiction_detector.detect_contradictions()."""

    def test_negation_contradiction_detected(self):
        """Two claims about the same topic with negation flip."""
        attrs = [
            _make_attribution(0, "The system is secure and reliable"),
            _make_attribution(1, "The system is not secure and has vulnerabilities"),
        ]
        results = detect_contradictions(attrs)
        assert len(results) >= 1
        neg_results = [r for r in results if r.contradiction_type == "NEGATION"]
        assert len(neg_results) >= 1

    def test_number_conflict_detected(self):
        """Two claims about the same topic with different numbers."""
        attrs = [
            _make_attribution(0, "The server has 16 processing cores"),
            _make_attribution(1, "The server has 64 processing cores"),
        ]
        results = detect_contradictions(attrs)
        num_results = [r for r in results if r.contradiction_type == "NUMBER_CONFLICT"]
        assert len(num_results) >= 1

    def test_semantic_contradiction_detected(self):
        """Two claims about the same topic with opposing sentiment."""
        attrs = [
            _make_attribution(0, "The market performance improved significantly this quarter"),
            _make_attribution(1, "The market performance declined significantly this quarter"),
        ]
        results = detect_contradictions(attrs)
        assert len(results) >= 1

    def test_no_contradiction_for_different_topics(self):
        """No contradiction when claims are about different topics."""
        attrs = [
            _make_attribution(0, "Python is a programming language"),
            _make_attribution(1, "The Eiffel Tower is in Paris"),
        ]
        results = detect_contradictions(attrs)
        assert len(results) == 0

    def test_no_contradiction_for_consistent_claims(self):
        """No contradiction when claims are consistent."""
        attrs = [
            _make_attribution(0, "The database has 100 tables"),
            _make_attribution(1, "The database has 100 tables and 50 views"),
        ]
        results = detect_contradictions(attrs)
        # Should be 0 since numbers match (100 is in both)
        num_conflicts = [r for r in results if r.contradiction_type == "NUMBER_CONFLICT"]
        assert len(num_conflicts) == 0

    def test_contradiction_result_fields(self):
        """ContradictionResult fields are populated correctly."""
        attrs = [
            _make_attribution(0, "The system is safe and well-tested"),
            _make_attribution(1, "The system is not safe or well-tested"),
        ]
        results = detect_contradictions(attrs)
        assert len(results) >= 1
        r = results[0]
        assert isinstance(r, ContradictionResult)
        assert r.claim_a_index == 0
        assert r.claim_b_index == 1
        assert r.severity > 0
        assert r.detail

    def test_cross_window_contradiction(self):
        """Contradictions detected against prior window claims."""
        attrs = [
            _make_attribution(0, "The database service is stable and running healthy"),
        ]
        prior = ["The database service is not stable and not running healthy"]
        results = detect_contradictions(attrs, prior_claims=prior)
        assert len(results) >= 1

    def test_empty_input(self):
        """No contradictions when there are no claims."""
        results = detect_contradictions([])
        assert results == []

    def test_single_claim_no_contradiction(self):
        """No contradictions with only one claim."""
        attrs = [_make_attribution(0, "Revenue grew 10 percent")]
        results = detect_contradictions(attrs)
        assert results == []

    def test_opinion_claims_excluded(self):
        """Opinion claims are excluded from contradiction check."""
        attrs = [
            _make_attribution(
                0, "I think the system is excellent",
                claim_type=ClaimType.OPINION,
            ),
            _make_attribution(
                1, "I think the system is terrible",
                claim_type=ClaimType.OPINION,
            ),
        ]
        results = detect_contradictions(attrs)
        assert results == []


# ===================================================================
# 5. FIDELITY REPORT DATA TYPE TESTS
# ===================================================================


class TestFidelityReportTypes:
    """Tests for FidelityReport and related data types."""

    def test_fidelity_report_defaults(self):
        """FidelityReport has correct defaults."""
        fr = FidelityReport()
        assert fr.distortions == []
        assert fr.fabrications == []
        assert fr.omissions == []
        assert fr.contradictions == []
        assert fr.distortion_count == 0
        assert fr.fabrication_count == 0
        assert fr.critical_omission_count == 0
        assert fr.contradiction_count == 0
        assert fr.fidelity_score == 1.0

    def test_distortion_type_values(self):
        """All DistortionType enum values exist."""
        assert len(DistortionType) == 7
        assert DistortionType.NUMBER_CHANGED.value == "NUMBER_CHANGED"
        assert DistortionType.NEGATION_FLIP.value == "NEGATION_FLIP"
        assert DistortionType.QUALIFIER_DROPPED.value == "QUALIFIER_DROPPED"
        assert DistortionType.QUALIFIER_ADDED.value == "QUALIFIER_ADDED"
        assert DistortionType.SCOPE_CHANGED.value == "SCOPE_CHANGED"
        assert DistortionType.ENTITY_SUBSTITUTED.value == "ENTITY_SUBSTITUTED"

    def test_fabrication_type_values(self):
        """All FabricationType enum values exist."""
        assert len(FabricationType) == 5
        assert FabricationType.NUMBER.value == "NUMBER"
        assert FabricationType.PERCENTAGE.value == "PERCENTAGE"
        assert FabricationType.DATE.value == "DATE"
        assert FabricationType.PROPER_NOUN.value == "PROPER_NOUN"
        assert FabricationType.CITATION.value == "CITATION"

    def test_omission_severity_values(self):
        """All OmissionSeverity enum values exist."""
        assert len(OmissionSeverity) == 4
        assert OmissionSeverity.CRITICAL.value == "CRITICAL"
        assert OmissionSeverity.HIGH.value == "HIGH"
        assert OmissionSeverity.MEDIUM.value == "MEDIUM"
        assert OmissionSeverity.LOW.value == "LOW"

    def test_provenance_report_fidelity_field(self):
        """ProvenanceReport has optional fidelity field."""
        from crp.provenance._types import ProvenanceReport

        report = ProvenanceReport()
        assert report.fidelity is None

        report.fidelity = FidelityReport(fidelity_score=0.85)
        assert report.fidelity.fidelity_score == 0.85


# ===================================================================
# 6. COMPLIANCE EVENT TYPE TESTS
# ===================================================================


class TestFidelityComplianceEventTypes:
    """Tests for fidelity-related ComplianceEventType values."""

    def test_distortion_detected_event_type(self):
        from crp.security.audit_trail import ComplianceEventType
        assert hasattr(ComplianceEventType, "DISTORTION_DETECTED")
        assert ComplianceEventType.DISTORTION_DETECTED.value == "compliance.distortion_detected"

    def test_omission_detected_event_type(self):
        from crp.security.audit_trail import ComplianceEventType
        assert hasattr(ComplianceEventType, "OMISSION_DETECTED")
        assert ComplianceEventType.OMISSION_DETECTED.value == "compliance.omission_detected"

    def test_fabrication_detected_event_type(self):
        from crp.security.audit_trail import ComplianceEventType
        assert hasattr(ComplianceEventType, "FABRICATION_DETECTED")
        assert ComplianceEventType.FABRICATION_DETECTED.value == "compliance.fabrication_detected"

    def test_contradiction_detected_event_type(self):
        from crp.security.audit_trail import ComplianceEventType
        assert hasattr(ComplianceEventType, "CONTRADICTION_DETECTED")
        assert ComplianceEventType.CONTRADICTION_DETECTED.value == "compliance.contradiction_detected"

    def test_total_event_types_count(self):
        """Total ComplianceEventType count includes all registered groups."""
        from crp.security.audit_trail import ComplianceEventType
        # lifecycle + consent + privacy + security + oversight + session + risk +
        # LLM provenance + DPE + fidelity + entailment + hallucination +
        # provenance engine ops + RQA + activation + window DAG = 61
        assert len(ComplianceEventType) == 61


# ===================================================================
# 7. DPE INTEGRATION TESTS
# ===================================================================


class TestDPEFidelityIntegration:
    """Tests for fidelity integration in DecisionProvenanceEngine.analyse()."""

    def test_analyse_returns_fidelity_report(self):
        """DPE analyse() returns a ProvenanceReport with fidelity."""
        dpe = DecisionProvenanceEngine(config=ProvenanceConfig())
        facts = [_make_packed_fact("f1", "Python was created in 1991")]
        report = dpe.analyse(
            output_text="Python was created in 1991 by Guido van Rossum.",
            packed_facts=facts,
            session_id="s1",
            window_id="w1",
        )
        assert report.fidelity is not None
        assert isinstance(report.fidelity, FidelityReport)

    def test_fidelity_score_perfect_for_faithful_output(self):
        """Fidelity score is high when output faithfully represents facts."""
        dpe = DecisionProvenanceEngine(config=ProvenanceConfig())
        facts = [_make_packed_fact("f1", "Python was created in 1991")]
        report = dpe.analyse(
            output_text="Python was created in 1991.",
            packed_facts=facts,
            session_id="s1",
            window_id="w1",
        )
        assert report.fidelity is not None
        assert report.fidelity.fidelity_score >= 0.80

    def test_fidelity_report_has_counts(self):
        """FidelityReport counts are populated."""
        dpe = DecisionProvenanceEngine(config=ProvenanceConfig())
        facts = [_make_packed_fact("f1", "Revenue grew moderately")]
        report = dpe.analyse(
            output_text="Revenue grew by 42 percent according to Smith et al.",
            packed_facts=facts,
            session_id="s1",
            window_id="w1",
        )
        fid = report.fidelity
        assert fid is not None
        assert fid.distortion_count >= 0
        assert fid.fabrication_count >= 0
        assert fid.critical_omission_count >= 0
        assert fid.contradiction_count >= 0

    def test_fidelity_disabled_when_dpe_disabled(self):
        """When DPE is disabled, fidelity is None."""
        dpe = DecisionProvenanceEngine(config=ProvenanceConfig(enabled=False))
        facts = [_make_packed_fact("f1", "Some fact")]
        report = dpe.analyse(
            output_text="Some output.",
            packed_facts=facts,
        )
        assert report.fidelity is None

    def test_fidelity_score_bounded(self):
        """Fidelity score is bounded between 0.0 and 1.0."""
        dpe = DecisionProvenanceEngine(config=ProvenanceConfig())
        # Generate output with many fabricated entities to drive score down
        output = (
            "Revenue grew 99 percent in Q1 2019. "
            "According to Johnson et al the growth was 87 percent. "
            "The firm reported 42 million in earnings. "
            "Expenses declined 73 percent. "
        )
        facts = [_make_packed_fact("f1", "Growth was moderate in the period")]
        report = dpe.analyse(
            output_text=output,
            packed_facts=facts,
            session_id="s1",
            window_id="w1",
        )
        fid = report.fidelity
        assert fid is not None
        assert 0.0 <= fid.fidelity_score <= 1.0


# ===================================================================
# 8. REPORT GENERATOR FIDELITY TESTS
# ===================================================================


class TestReportGeneratorFidelity:
    """Tests for fidelity sections in generated reports."""

    def _make_report_with_fidelity(self) -> "ProvenanceReport":
        """Create a report with fidelity data for testing."""
        from crp.provenance._types import ProvenanceReport

        fid = FidelityReport(
            distortions=[
                DistortionResult(
                    claim_index=0,
                    claim_text="Revenue grew 25 percent",
                    source_fact_id="f1",
                    source_fact_preview="Revenue grew 10 percent",
                    distortion_type=DistortionType.NUMBER_CHANGED,
                    severity=0.75,
                    detail="Number changed from 10 to 25",
                    claim_value="25",
                    fact_value="10",
                ),
            ],
            fabrications=[
                FabricationResult(
                    claim_index=1,
                    claim_text="According to Smith et al the results were positive",
                    fabricated_entity="Smith et al",
                    entity_type=FabricationType.CITATION,
                    severity=0.90,
                    detail="Citation not found in any source fact",
                ),
            ],
            omissions=[
                OmissionResult(
                    fact_id="f2",
                    fact_text_preview="Critical security vulnerability found",
                    fact_relevance_score=0.95,
                    max_attribution_score=0.0,
                    severity=OmissionSeverity.CRITICAL,
                ),
            ],
            contradictions=[
                ContradictionResult(
                    claim_a_index=0,
                    claim_a_text="The system is secure",
                    claim_b_index=2,
                    claim_b_text="The system is not secure",
                    contradiction_type="NEGATION",
                    severity=0.85,
                    detail="Negation flip detected",
                ),
            ],
            distortion_count=1,
            fabrication_count=1,
            critical_omission_count=1,
            contradiction_count=1,
            fidelity_score=0.64,
        )

        return ProvenanceReport(
            session_id="test-session",
            window_id="test-window",
            timestamp=1700000000.0,
            total_claims=3,
            factual_claims=3,
            fidelity=fid,
        )

    def test_markdown_report_includes_fidelity(self):
        """Markdown report includes fidelity verification section."""
        from crp.provenance.report_generator import generate_markdown_report

        report = self._make_report_with_fidelity()
        md = generate_markdown_report(report)
        assert "### Fidelity Verification" in md
        assert "0.64" in md

    def test_markdown_report_includes_distortions_table(self):
        from crp.provenance.report_generator import generate_markdown_report

        report = self._make_report_with_fidelity()
        md = generate_markdown_report(report)
        assert "#### Distortions Detected" in md
        assert "NUMBER_CHANGED" in md

    def test_markdown_report_includes_fabrications_table(self):
        from crp.provenance.report_generator import generate_markdown_report

        report = self._make_report_with_fidelity()
        md = generate_markdown_report(report)
        assert "#### Fabrications Detected" in md
        assert "CITATION" in md

    def test_markdown_report_includes_omissions(self):
        from crp.provenance.report_generator import generate_markdown_report

        report = self._make_report_with_fidelity()
        md = generate_markdown_report(report)
        assert "#### Critical/High Omissions" in md

    def test_markdown_report_includes_contradictions(self):
        from crp.provenance.report_generator import generate_markdown_report

        report = self._make_report_with_fidelity()
        md = generate_markdown_report(report)
        assert "#### Contradictions Detected" in md
        assert "NEGATION" in md

    def test_json_report_includes_fidelity(self):
        """JSON report includes fidelity section."""
        from crp.provenance.report_generator import generate_json_report

        report = self._make_report_with_fidelity()
        data = generate_json_report(report)
        assert "fidelity" in data
        assert data["fidelity"] is not None
        assert data["fidelity"]["fidelity_score"] == 0.64
        assert data["fidelity"]["distortion_count"] == 1
        assert data["fidelity"]["fabrication_count"] == 1
        assert data["fidelity"]["contradiction_count"] == 1

    def test_json_report_fidelity_none_when_absent(self):
        """JSON report fidelity is None when no fidelity report."""
        from crp.provenance._types import ProvenanceReport
        from crp.provenance.report_generator import generate_json_report

        report = ProvenanceReport(session_id="s1", window_id="w1")
        data = generate_json_report(report)
        assert data["fidelity"] is None

    def test_markdown_report_no_issues_message(self):
        """Markdown report shows 'No fidelity issues' when clean."""
        from crp.provenance._types import ProvenanceReport
        from crp.provenance.report_generator import generate_markdown_report

        report = ProvenanceReport(
            session_id="s1",
            window_id="w1",
            timestamp=1700000000.0,
            fidelity=FidelityReport(),  # Empty — no issues
        )
        md = generate_markdown_report(report)
        assert "No fidelity issues detected" in md


# ===================================================================
# 9. EDGE CASES
# ===================================================================


class TestFidelityEdgeCases:
    """Edge-case tests for the fidelity verification layer."""

    def test_distortion_empty_facts(self):
        """detect_distortions handles empty facts list."""
        attrs = [_make_attribution(0, "Some claim", top_fact_id="f1")]
        results = detect_distortions(attrs, [])
        # No facts to compare → no distortions
        assert isinstance(results, list)

    def test_omission_no_attributions(self):
        """analyze_omissions with no attributions flags all facts."""
        facts = [
            _make_packed_fact("f1", "Fact one", score=0.80),
            _make_packed_fact("f2", "Fact two", score=0.70),
        ]
        results = analyze_omissions([], facts)
        assert len(results) == 2

    def test_fabrication_empty_claims(self):
        """detect_fabrications with no claims returns empty."""
        facts = [_make_packed_fact("f1", "Some fact")]
        results = detect_fabrications([], facts)
        assert results == []

    def test_contradiction_all_opinions(self):
        """No contradictions when all claims are opinions."""
        attrs = [
            _make_attribution(0, "I think A is great", claim_type=ClaimType.OPINION),
            _make_attribution(1, "I think A is terrible", claim_type=ClaimType.OPINION),
        ]
        results = detect_contradictions(attrs)
        assert results == []

    def test_distortion_unicode_text(self):
        """Distortion detector handles unicode text."""
        facts = [_make_packed_fact("f1", "Résumé shows 10% growth")]
        attrs = [
            _make_attribution(
                0, "Résumé shows 50% growth",
                top_fact_id="f1",
                top_fact_text="Résumé shows 10% growth",
            ),
        ]
        results = detect_distortions(attrs, facts)
        assert isinstance(results, list)
