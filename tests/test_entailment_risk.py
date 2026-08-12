# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Tests for Semantic Entailment Verification & Hallucination Risk Scoring.

Two innovation modules under test:
  1. **Entailment Verifier** — ML-powered NLI (mocked) + heuristic fallback
  2. **Hallucination Risk Scorer** — composite per-claim risk assessment

All tests mock the NLI model to avoid loading the ~80 MB cross-encoder.
Tests use deterministic predictions via the ``_model_override`` parameter.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import pytest

from crp.envelope.packer import PackedFact
from crp.provenance._types import (
    AttributionType,
    ClaimAttribution,
    ClaimRiskAssessment,
    ClaimType,
    DistortionResult,
    DistortionType,
    EntailmentLabel,
    EntailmentResult,
    FabricationResult,
    FabricationType,
    FactScore,
    FidelityReport,
    HallucinationRisk,
    HallucinationRiskReport,
    ProvenanceConfig,
)
from crp.provenance.entailment_verifier import (
    _classify_from_probs,
    _content_words,
    _has_negation,
    _heuristic_entailment,
    reset_model_cache,
    verify_entailment,
)
from crp.provenance.hallucination_scorer import (
    compute_specificity,
    score_hallucination_risk,
)


# ===================================================================
# Helper factories
# ===================================================================


def _fact(fact_id: str, text: str, score: float = 0.80) -> PackedFact:
    """Create a PackedFact for testing."""
    return PackedFact(fact_id=fact_id, text=text, score=score, tokens=len(text.split()))


def _attr(
    claim_text: str,
    *,
    index: int = 0,
    claim_type: ClaimType = ClaimType.FACTUAL_CLAIM,
    attribution_type: AttributionType = AttributionType.CONTEXT_GROUNDED,
    top_score: float = 0.80,
    fact_id: str = "fact-1",
    fact_preview: str = "",
) -> ClaimAttribution:
    """Create a ClaimAttribution for testing."""
    facts = []
    if fact_id:
        facts.append(FactScore(
            fact_id=fact_id,
            fact_text_preview=fact_preview or claim_text[:60],
            composite_score=top_score,
        ))
    return ClaimAttribution(
        claim_text=claim_text,
        claim_index=index,
        claim_type=claim_type,
        attribution_type=attribution_type,
        top_score=top_score,
        confidence=top_score,
        attributed_facts=facts,
    )


class MockNLIModel:
    """Mock NLI cross-encoder that returns deterministic scores.

    Scores format: [contradiction, entailment, neutral] (raw logits).
    """

    def __init__(self, scores_map: dict[str, list[float]] | None = None,
                 default_scores: list[float] | None = None):
        self._scores_map = scores_map or {}
        self._default = default_scores or [0.0, 2.0, 0.0]  # ENTAILED by default
        self.call_count = 0

    def predict(self, pairs: list[tuple[str, str]]) -> list[list[float]]:
        self.call_count += 1
        results = []
        for premise, hypothesis in pairs:
            key = hypothesis[:50]
            scores = self._scores_map.get(key, self._default)
            results.append(scores)
        return results


class FailingNLIModel:
    """Mock NLI model that raises on predict()."""

    def predict(self, pairs: list) -> list:
        raise RuntimeError("GPU out of memory")


# ===================================================================
# PART 1: Entailment Verifier — Heuristic Tests
# ===================================================================


class TestHeuristicHelpers:
    """Test low-level heuristic helper functions."""

    def test_content_words_removes_stopwords(self):
        words = _content_words("The server is running on the cloud")
        assert "the" not in words
        assert "server" in words
        assert "running" in words
        assert "cloud" in words

    def test_content_words_removes_short_words(self):
        words = _content_words("I am at it")
        assert len(words) == 0

    def test_has_negation_positive(self):
        assert _has_negation("The system is not secure")
        assert _has_negation("It doesn't work")
        assert _has_negation("Never use this approach")

    def test_has_negation_negative(self):
        assert not _has_negation("The system is secure")
        assert not _has_negation("It works perfectly fine")

    def test_classify_entailed(self):
        label, conf = _classify_from_probs(0.8, 0.1, 0.1)
        assert label == EntailmentLabel.ENTAILED
        assert conf == 0.8

    def test_classify_contradiction(self):
        label, conf = _classify_from_probs(0.1, 0.8, 0.1)
        assert label == EntailmentLabel.CONTRADICTION
        assert conf == 0.8

    def test_classify_neutral(self):
        label, conf = _classify_from_probs(0.1, 0.1, 0.8)
        assert label == EntailmentLabel.NEUTRAL
        assert conf == 0.8


class TestHeuristicEntailment:
    """Test the heuristic entailment fallback."""

    def test_high_overlap_entailed(self):
        claim = "The server uses AES-256 encryption for all data"
        fact = "The server employs AES-256 encryption for all stored data"
        ent, con, neu = _heuristic_entailment(claim, fact)
        assert ent > con
        assert ent > neu

    def test_negation_flip_contradiction(self):
        claim = "The system is not secure against attacks"
        fact = "The system is secure against attacks"
        ent, con, neu = _heuristic_entailment(claim, fact)
        assert con > ent
        assert con > neu

    def test_low_overlap_neutral(self):
        claim = "Revenue grew significantly in Q4 2024"
        fact = "The server uses AES-256 encryption"
        ent, con, neu = _heuristic_entailment(claim, fact)
        assert neu > ent
        assert neu > con

    def test_empty_claim_neutral(self):
        ent, con, neu = _heuristic_entailment("", "some fact text here")
        assert neu == 1.0
        assert ent == 0.0
        assert con == 0.0

    def test_medium_overlap(self):
        claim = "The encryption standard provides good security"
        fact = "AES-256 encryption standard ensures strong security"
        ent, con, neu = _heuristic_entailment(claim, fact)
        # Should have moderate entailment
        assert ent > 0.2


# ===================================================================
# PART 2: Entailment Verifier — Model-powered Tests (mocked)
# ===================================================================


class TestEntailmentWithMockModel:
    """Test verify_entailment with mocked NLI model."""

    def setup_method(self):
        reset_model_cache()

    def test_entailed_claim_with_model(self):
        """Claim semantically follows from fact → ENTAILED."""
        claim = "The server uses AES-256 encryption"
        fact_text = "The server employs AES-256 encryption for all stored data"

        attributions = [_attr(claim, fact_id="f1", fact_preview=fact_text)]
        facts = [_fact("f1", fact_text)]

        # Model returns strong entailment logits [con, ent, neu]
        model = MockNLIModel(default_scores=[0.0, 3.0, 0.0])
        results = verify_entailment(
            attributions, facts, _model_override=model,
        )

        assert len(results) == 1
        assert results[0].label == EntailmentLabel.ENTAILED
        assert results[0].used_model is True
        assert results[0].entailment_score > 0.5
        assert model.call_count == 1

    def test_contradiction_claim_with_model(self):
        """Claim contradicts fact → CONTRADICTION."""
        claim = "The system is completely insecure"
        fact_text = "The system has robust security measures in place"

        attributions = [_attr(claim, fact_id="f1", fact_preview=fact_text)]
        facts = [_fact("f1", fact_text)]

        # Model returns strong contradiction [con, ent, neu]
        model = MockNLIModel(default_scores=[3.0, 0.0, 0.0])
        results = verify_entailment(
            attributions, facts, _model_override=model,
        )

        assert len(results) == 1
        assert results[0].label == EntailmentLabel.CONTRADICTION
        assert results[0].contradiction_score > 0.5

    def test_neutral_claim_with_model(self):
        """Claim unrelated to fact → NEUTRAL."""
        claim = "Revenue grew 23% in Q4"
        fact_text = "The encryption algorithm uses 256-bit keys"

        attributions = [_attr(claim, fact_id="f1", fact_preview=fact_text)]
        facts = [_fact("f1", fact_text)]

        model = MockNLIModel(default_scores=[0.0, 0.0, 3.0])
        results = verify_entailment(
            attributions, facts, _model_override=model,
        )

        assert len(results) == 1
        assert results[0].label == EntailmentLabel.NEUTRAL
        assert results[0].neutral_score > 0.5

    def test_skips_parametric_claims(self):
        """Only verifies CONTEXT_GROUNDED and MIXED claims."""
        attributions = [
            _attr("Training data claim", attribution_type=AttributionType.PARAMETRIC),
        ]
        facts = [_fact("f1", "some fact")]

        model = MockNLIModel()
        results = verify_entailment(
            attributions, facts, _model_override=model,
        )
        assert len(results) == 0
        assert model.call_count == 0

    def test_skips_opinion_claims(self):
        """Only verifies FACTUAL_CLAIM and HEDGE types."""
        attributions = [
            _attr("I think this is great", claim_type=ClaimType.OPINION),
        ]
        facts = [_fact("f1", "some fact")]

        model = MockNLIModel()
        results = verify_entailment(
            attributions, facts, _model_override=model,
        )
        assert len(results) == 0

    def test_mixed_claim_is_verified(self):
        """MIXED attribution claims should be verified."""
        attributions = [
            _attr("Mixed source claim", attribution_type=AttributionType.MIXED,
                  fact_id="f1", fact_preview="Original fact"),
        ]
        facts = [_fact("f1", "Original fact")]

        model = MockNLIModel(default_scores=[0.0, 2.0, 0.0])
        results = verify_entailment(
            attributions, facts, _model_override=model,
        )
        assert len(results) == 1

    def test_hedge_claim_is_verified(self):
        """HEDGE type claims should be verified."""
        attributions = [
            _attr("This might indicate a trend", claim_type=ClaimType.HEDGE,
                  fact_id="f1", fact_preview="Data shows a trend"),
        ]
        facts = [_fact("f1", "Data shows a significant upward trend")]

        model = MockNLIModel(default_scores=[0.0, 2.0, 0.0])
        results = verify_entailment(
            attributions, facts, _model_override=model,
        )
        assert len(results) == 1

    def test_multiple_claims_batch(self):
        """Multiple claims are batched into one model.predict() call."""
        attributions = [
            _attr("Claim A about security", index=0, fact_id="f1",
                  fact_preview="Security fact A"),
            _attr("Claim B about encryption", index=1, fact_id="f2",
                  fact_preview="Encryption fact B"),
            _attr("Claim C about storage", index=2, fact_id="f3",
                  fact_preview="Storage fact C"),
        ]
        facts = [
            _fact("f1", "Security fact A"),
            _fact("f2", "Encryption fact B"),
            _fact("f3", "Storage fact C"),
        ]

        model = MockNLIModel(default_scores=[0.0, 2.0, 0.0])
        results = verify_entailment(
            attributions, facts, _model_override=model,
        )
        assert len(results) == 3
        assert model.call_count == 1  # Single batch call

    def test_graceful_fallback_on_predict_failure(self):
        """If model.predict() throws, falls back to heuristic."""
        attributions = [
            _attr("The server uses AES-256 encryption",
                  fact_id="f1", fact_preview="The server uses AES-256 encryption"),
        ]
        facts = [_fact("f1", "The server uses AES-256 encryption")]

        model = FailingNLIModel()
        results = verify_entailment(
            attributions, facts, _model_override=model,
        )
        assert len(results) == 1
        assert results[0].used_model is False  # Fell back to heuristic

    def test_disabled_returns_empty(self):
        """When entailment_enabled=False, returns empty list."""
        config = ProvenanceConfig(entailment_enabled=False)
        attributions = [_attr("Some claim")]
        facts = [_fact("f1", "Some fact")]

        results = verify_entailment(
            attributions, facts, config=config,
        )
        assert results == []

    def test_no_grounded_claims_returns_empty(self):
        """If no claims match criteria, returns empty list."""
        attributions = [
            _attr("Opinion", claim_type=ClaimType.OPINION),
            _attr("Procedure", claim_type=ClaimType.PROCEDURAL),
            _attr("Connective", claim_type=ClaimType.CONNECTIVE),
        ]
        facts = [_fact("f1", "Some fact")]

        results = verify_entailment(attributions, facts)
        assert results == []


# ===================================================================
# PART 3: Entailment Verifier — Adversarial Tests
# ===================================================================


class TestEntailmentAdversarial:
    """Adversarial scenarios that test semantic-level detection.

    These test the heuristic fallback since no real model is loaded.
    The heuristic should at least flag the most obvious cases.
    """

    def test_negation_flip_detected(self):
        """'is secure' → 'is not secure' — heuristic should catch."""
        claim = "The application is not secure against SQL injection"
        fact = "The application is secure against SQL injection attacks"

        ent, con, neu = _heuristic_entailment(claim, fact)
        assert con > ent, "Negation flip should produce contradiction signal"

    def test_identical_text_entailed(self):
        """Exact same text → strong entailment."""
        text = "Revenue grew 23.4% in Q3 2024 according to the report"
        ent, con, neu = _heuristic_entailment(text, text)
        assert ent > 0.5

    def test_completely_unrelated_neutral(self):
        """Totally different topics → neutral."""
        claim = "The weather forecast predicts heavy rain tomorrow"
        fact = "Database sharding improves query performance by 40%"
        ent, con, neu = _heuristic_entailment(claim, fact)
        assert neu > ent
        assert neu > con

    def test_paraphrase_moderate_entailment(self):
        """Paraphrase preserving meaning → moderate entailment score."""
        claim = "Encryption ensures data remains protected from unauthorized access"
        fact = "AES-256 encryption protects data from unauthorized access attempts"
        ent, con, neu = _heuristic_entailment(claim, fact)
        # Should have some entailment signal due to shared words
        assert ent > 0.1

    def test_double_negation(self):
        """Double negation — both sides negated → shouldn't flag contradiction."""
        claim = "The system is not unable to process requests"
        fact = "The system is not unable to handle incoming requests"
        ent, con, neu = _heuristic_entailment(claim, fact)
        # Both have negation, no flip → should not be strong contradiction
        assert con < 0.5


# ===================================================================
# PART 4: Claim Specificity Analysis
# ===================================================================


class TestSpecificity:
    """Test the claim specificity scoring for risk assessment."""

    def test_vague_claim_low_specificity(self):
        specificity = compute_specificity("Performance improved significantly")
        assert specificity < 0.3

    def test_number_increases_specificity(self):
        specificity = compute_specificity("Revenue grew 23.4% in Q3 2024")
        assert specificity > 0.3

    def test_highly_specific_claim(self):
        specificity = compute_specificity(
            "According to Deloitte, revenue grew 23.4% to $4.2 billion "
            "in Q3 2024, exceeding analyst expectations"
        )
        assert specificity > 0.6

    def test_measurements_increase_specificity(self):
        specificity = compute_specificity("The dosage was 500mg administered every 12 hours")
        assert specificity > 0.3

    def test_proper_nouns_increase_specificity(self):
        specificity = compute_specificity(
            "According to Smith and Johnson at Stanford University"
        )
        assert specificity > 0.3

    def test_empty_claim(self):
        assert compute_specificity("") == 0.0


# ===================================================================
# PART 5: Hallucination Risk Scorer
# ===================================================================


class TestHallucinationRiskScorer:
    """Test the composite risk scoring logic."""

    def test_well_grounded_claim_low_risk(self):
        """High attribution + no fidelity issues + entailment → LOW risk."""
        attributions = [
            _attr("The server uses AES-256 encryption", top_score=0.90),
        ]
        entailment = [
            EntailmentResult(
                claim_index=0, claim_text="The server uses AES-256",
                fact_id="f1", label=EntailmentLabel.ENTAILED,
                entailment_score=0.85, contradiction_score=0.05,
                neutral_score=0.10, confidence=0.85, used_model=True,
            ),
        ]

        report = score_hallucination_risk(
            attributions,
            entailment_results=entailment,
        )

        assert len(report.assessments) == 1
        assert report.assessments[0].risk_level == HallucinationRisk.LOW
        assert report.assessments[0].risk_score < 0.25

    def test_parametric_claim_higher_risk(self):
        """Parametric knowledge → higher risk due to no grounding."""
        attributions = [
            _attr("Revenue grew 23% this quarter",
                  attribution_type=AttributionType.PARAMETRIC, top_score=0.20),
        ]

        report = score_hallucination_risk(attributions)

        assert len(report.assessments) == 1
        assert report.assessments[0].risk_level in (
            HallucinationRisk.MEDIUM, HallucinationRisk.HIGH, HallucinationRisk.CRITICAL,
        )
        assert report.assessments[0].risk_score > 0.3
        assert any("Parametric" in f for f in report.assessments[0].risk_factors)

    def test_uncertain_claim_high_risk(self):
        """Uncertain attribution → high risk."""
        attributions = [
            _attr("Revenue grew 23.4% in Q4 2024 according to Deloitte",
                  attribution_type=AttributionType.UNCERTAIN, top_score=0.10),
        ]

        report = score_hallucination_risk(attributions)

        assert report.assessments[0].risk_level in (
            HallucinationRisk.HIGH, HallucinationRisk.CRITICAL,
        )
        assert any("Uncertain" in f for f in report.assessments[0].risk_factors)

    def test_contradiction_entailment_high_risk(self):
        """NLI contradiction → dramatically increased risk."""
        attributions = [
            _attr("The system is completely insecure", top_score=0.70),
        ]
        entailment = [
            EntailmentResult(
                claim_index=0, claim_text="The system is completely insecure",
                fact_id="f1", label=EntailmentLabel.CONTRADICTION,
                entailment_score=0.05, contradiction_score=0.85,
                neutral_score=0.10, confidence=0.85, used_model=True,
            ),
        ]

        report = score_hallucination_risk(
            attributions, entailment_results=entailment,
        )

        assert report.assessments[0].risk_score > 0.3
        assert any("CONTRADICTION" in f for f in report.assessments[0].risk_factors)

    def test_distortion_increases_risk(self):
        """Fidelity distortions should increase risk score."""
        attributions = [_attr("Revenue grew 25%", index=0)]
        fidelity = FidelityReport(
            distortions=[
                DistortionResult(
                    claim_index=0, claim_text="Revenue grew 25%",
                    distortion_type=DistortionType.NUMBER_CHANGED,
                    severity=0.80, detail="10% → 25%",
                    claim_value="25%", fact_value="10%",
                ),
            ],
            distortion_count=1,
            fidelity_score=0.90,
        )

        report = score_hallucination_risk(
            attributions, fidelity=fidelity,
        )

        assert any("Distortion" in f for f in report.assessments[0].risk_factors)

    def test_fabrication_increases_risk(self):
        """Fabricated entities should increase risk score."""
        attributions = [_attr("According to Dr Smith et al 2024", index=0)]
        fidelity = FidelityReport(
            fabrications=[
                FabricationResult(
                    claim_index=0, claim_text="According to Dr Smith et al 2024",
                    fabricated_entity="Dr Smith et al 2024",
                    entity_type=FabricationType.CITATION,
                    severity=0.70,
                ),
            ],
            fabrication_count=1,
            fidelity_score=0.92,
        )

        report = score_hallucination_risk(
            attributions, fidelity=fidelity,
        )

        assert any("Fabrication" in f for f in report.assessments[0].risk_factors)

    def test_opinion_claim_low_risk(self):
        """Opinion claims should be LOW risk regardless."""
        attributions = [
            _attr("I think this approach is reasonable",
                  claim_type=ClaimType.OPINION),
        ]

        report = score_hallucination_risk(attributions)

        assert report.assessments[0].risk_level == HallucinationRisk.LOW
        assert report.assessments[0].risk_score == 0.0

    def test_connective_claim_low_risk(self):
        """Connective claims should be LOW risk."""
        attributions = [
            _attr("Furthermore, the following points apply",
                  claim_type=ClaimType.CONNECTIVE),
        ]

        report = score_hallucination_risk(attributions)

        assert report.assessments[0].risk_level == HallucinationRisk.LOW

    def test_window_level_aggregation(self):
        """Window-level risk should reflect worst claim."""
        attributions = [
            _attr("Safe claim", index=0, top_score=0.90),
            _attr("Revenue grew 23% per Deloitte Q4 2024",
                  index=1, attribution_type=AttributionType.UNCERTAIN,
                  top_score=0.05),
        ]
        entailment = [
            EntailmentResult(
                claim_index=0, claim_text="Safe claim", fact_id="f1",
                label=EntailmentLabel.ENTAILED,
                entailment_score=0.90, contradiction_score=0.05,
                neutral_score=0.05, confidence=0.90, used_model=True,
            ),
        ]

        report = score_hallucination_risk(
            attributions, entailment_results=entailment,
        )

        # Window level should be at least MEDIUM due to the uncertain claim
        assert report.window_risk_level in (
            HallucinationRisk.MEDIUM, HallucinationRisk.HIGH, HallucinationRisk.CRITICAL,
        )

    def test_disabled_returns_empty(self):
        """When risk_scoring_enabled=False, returns empty report."""
        config = ProvenanceConfig(risk_scoring_enabled=False)
        report = score_hallucination_risk(
            [_attr("Some claim")], config=config,
        )
        assert report.assessments == []
        assert report.mean_risk_score == 0.0

    def test_highly_specific_ungrounded_is_critical(self):
        """Highly specific claim with no grounding → CRITICAL risk."""
        attributions = [
            _attr(
                "The study by Johnson et al at Stanford showed 99.7% accuracy "
                "on 50,000 samples in March 2024 using 128GB RAM",
                attribution_type=AttributionType.UNCERTAIN,
                top_score=0.05,
            ),
        ]

        report = score_hallucination_risk(attributions)

        # Very specific + uncertain → should be HIGH or CRITICAL
        assert report.assessments[0].risk_level in (
            HallucinationRisk.HIGH, HallucinationRisk.CRITICAL,
        )
        assert report.assessments[0].specificity_signal > 0.5

    def test_risk_factors_human_readable(self):
        """Risk factors should be human-readable strings."""
        attributions = [
            _attr("Unsourced claim about revenue",
                  attribution_type=AttributionType.PARAMETRIC, top_score=0.20),
        ]
        entailment = [
            EntailmentResult(
                claim_index=0, claim_text="Unsourced claim",
                fact_id="f1", label=EntailmentLabel.NEUTRAL,
                entailment_score=0.10, contradiction_score=0.10,
                neutral_score=0.80, confidence=0.80, used_model=True,
            ),
        ]

        report = score_hallucination_risk(
            attributions, entailment_results=entailment,
        )

        factors = report.assessments[0].risk_factors
        assert len(factors) > 0
        for f in factors:
            assert isinstance(f, str)
            assert len(f) > 5  # Not empty/trivial

    def test_custom_weights(self):
        """Custom risk weights should affect scores."""
        attributions = [
            _attr("Some factual claim", top_score=0.50),
        ]

        # Default weights
        r1 = score_hallucination_risk(attributions)

        # Heavy emphasis on attribution weight
        config = ProvenanceConfig(
            risk_weight_attribution=0.60,
            risk_weight_fidelity=0.20,
            risk_weight_entailment=0.10,
            risk_weight_specificity=0.10,
        )
        r2 = score_hallucination_risk(attributions, config=config)

        # Scores should differ with different weights
        assert r1.assessments[0].risk_score != r2.assessments[0].risk_score


# ===================================================================
# PART 6: Risk Scorer — Multiple-signal Calibration Tests
# ===================================================================


class TestRiskCalibration:
    """Verify risk scores are calibrated (monotonic with risk)."""

    def test_better_attribution_reduces_risk(self):
        """Higher attribution score → lower risk."""
        low_attr = [_attr("Claim", top_score=0.20)]
        high_attr = [_attr("Claim", top_score=0.90)]

        r_low = score_hallucination_risk(low_attr)
        r_high = score_hallucination_risk(high_attr)

        assert r_low.assessments[0].risk_score > r_high.assessments[0].risk_score

    def test_entailment_reduces_risk(self):
        """Strong entailment → lower risk."""
        attributions = [_attr("Claim about security", top_score=0.60)]

        no_ent = score_hallucination_risk(attributions)

        with_ent = score_hallucination_risk(
            attributions,
            entailment_results=[
                EntailmentResult(
                    claim_index=0, claim_text="Claim about security",
                    fact_id="f1", label=EntailmentLabel.ENTAILED,
                    entailment_score=0.90, contradiction_score=0.05,
                    neutral_score=0.05, confidence=0.90, used_model=True,
                ),
            ],
        )

        assert with_ent.assessments[0].risk_score < no_ent.assessments[0].risk_score

    def test_contradiction_increases_risk(self):
        """NLI contradiction → higher risk than entailment."""
        attributions = [_attr("Claim", top_score=0.60)]

        r_ent = score_hallucination_risk(
            attributions,
            entailment_results=[
                EntailmentResult(
                    claim_index=0, claim_text="Claim", fact_id="f1",
                    label=EntailmentLabel.ENTAILED,
                    entailment_score=0.90, contradiction_score=0.05,
                    neutral_score=0.05, confidence=0.90, used_model=True,
                ),
            ],
        )

        r_con = score_hallucination_risk(
            attributions,
            entailment_results=[
                EntailmentResult(
                    claim_index=0, claim_text="Claim", fact_id="f1",
                    label=EntailmentLabel.CONTRADICTION,
                    entailment_score=0.05, contradiction_score=0.85,
                    neutral_score=0.10, confidence=0.85, used_model=True,
                ),
            ],
        )

        assert r_con.assessments[0].risk_score > r_ent.assessments[0].risk_score

    def test_risk_score_bounded_0_1(self):
        """Risk scores should always be in [0.0, 1.0]."""
        # Worst case: uncertain, high specificity, contradiction
        attributions = [
            _attr(
                "According to Johnson at Stanford, the 99.7% accuracy "
                "on 50000 samples in March 2024 is remarkable",
                attribution_type=AttributionType.UNCERTAIN, top_score=0.0,
            ),
        ]
        entailment = [
            EntailmentResult(
                claim_index=0, claim_text="claim", fact_id="f1",
                label=EntailmentLabel.CONTRADICTION,
                entailment_score=0.0, contradiction_score=1.0,
                neutral_score=0.0, confidence=1.0, used_model=True,
            ),
        ]

        report = score_hallucination_risk(
            attributions, entailment_results=entailment,
        )

        for a in report.assessments:
            assert 0.0 <= a.risk_score <= 1.0

    def test_zero_factual_claims(self):
        """All non-factual claims → empty factual assessments."""
        attributions = [
            _attr("Just an opinion", claim_type=ClaimType.OPINION),
        ]
        report = score_hallucination_risk(attributions)
        assert report.window_risk_level == HallucinationRisk.LOW
        assert report.mean_risk_score == 0.0


# ===================================================================
# PART 7: End-to-end DPE pipeline integration
# ===================================================================


class TestDPEIntegration:
    """Test that entailment + risk flow through the DPE pipeline."""

    def setup_method(self):
        reset_model_cache()

    def test_pipeline_produces_entailment_results(self):
        """Full DPE pipeline should produce entailment results."""
        from crp.provenance import DecisionProvenanceEngine

        dpe = DecisionProvenanceEngine(
            config=ProvenanceConfig(entailment_enabled=True),
        )
        facts = [
            _fact("f1", "The server uses AES-256 encryption for data at rest"),
            _fact("f2", "Authentication requires two-factor verification"),
        ]

        report = dpe.analyse(
            output_text=(
                "The server uses AES-256 encryption for data at rest. "
                "Authentication requires two-factor verification. "
                "This is overall a good approach."
            ),
            packed_facts=facts,
        )

        # Should have run (even if heuristic only — no real model loaded)
        assert report is not None
        assert isinstance(report.entailment_results, list)

    def test_pipeline_produces_risk_report(self):
        """Full DPE pipeline should produce risk report."""
        from crp.provenance import DecisionProvenanceEngine

        dpe = DecisionProvenanceEngine()
        facts = [_fact("f1", "System uptime is 99.9%")]

        report = dpe.analyse(
            output_text="System uptime is 99.9%. This is adequate.",
            packed_facts=facts,
        )

        assert report.risk_report is not None
        assert isinstance(report.risk_report, HallucinationRiskReport)

    def test_disabled_pipeline_no_entailment(self):
        """When entailment disabled, no entailment results."""
        from crp.provenance import DecisionProvenanceEngine

        dpe = DecisionProvenanceEngine(
            config=ProvenanceConfig(entailment_enabled=False),
        )
        report = dpe.analyse(
            output_text="Some claim about encryption.",
            packed_facts=[_fact("f1", "Encryption is used")],
        )

        assert report.entailment_results == []


# ===================================================================
# PART 8: Report Generator Tests
# ===================================================================


class TestReportGeneration:
    """Test that reports include entailment and risk sections."""

    def test_markdown_includes_entailment_section(self):
        """Markdown report should have entailment section."""
        from crp.provenance.report_generator import generate_markdown_report
        from crp.provenance._types import ProvenanceReport

        report = ProvenanceReport(
            session_id="test-session",
            window_id="test-window",
            timestamp=0.0,
            total_claims=1,
            entailment_results=[
                EntailmentResult(
                    claim_index=0, claim_text="Some claim",
                    fact_id="f1", fact_text_preview="Some fact",
                    label=EntailmentLabel.ENTAILED,
                    entailment_score=0.85, contradiction_score=0.05,
                    neutral_score=0.10, confidence=0.85, used_model=True,
                ),
            ],
        )

        md = generate_markdown_report(report)
        assert "Semantic Entailment" in md
        assert "entailed" in md.lower() or "0 contradictions" in md

    def test_markdown_shows_contradictions(self):
        """Contradictions should appear prominently in markdown."""
        from crp.provenance.report_generator import generate_markdown_report
        from crp.provenance._types import ProvenanceReport

        report = ProvenanceReport(
            session_id="s", window_id="w", timestamp=0.0,
            total_claims=1,
            entailment_results=[
                EntailmentResult(
                    claim_index=0, claim_text="The system is insecure",
                    fact_id="f1", fact_text_preview="The system is secure",
                    label=EntailmentLabel.CONTRADICTION,
                    entailment_score=0.05, contradiction_score=0.85,
                    neutral_score=0.10, confidence=0.85, used_model=True,
                ),
            ],
        )

        md = generate_markdown_report(report)
        assert "contradiction" in md.lower()

    def test_markdown_includes_risk_section(self):
        """Risk section should appear in markdown."""
        from crp.provenance.report_generator import generate_markdown_report
        from crp.provenance._types import ProvenanceReport

        report = ProvenanceReport(
            session_id="s", window_id="w", timestamp=0.0,
            total_claims=1,
            risk_report=HallucinationRiskReport(
                assessments=[
                    ClaimRiskAssessment(
                        claim_index=0, claim_text="Risky claim",
                        risk_level=HallucinationRisk.HIGH,
                        risk_score=0.65,
                        risk_factors=["Uncertain attribution"],
                    ),
                ],
                high_risk_count=1,
                mean_risk_score=0.65,
                window_risk_level=HallucinationRisk.HIGH,
            ),
        )

        md = generate_markdown_report(report)
        assert "Hallucination Risk" in md
        assert "HIGH" in md

    def test_json_includes_entailment(self):
        """JSON report should include entailment data."""
        from crp.provenance.report_generator import generate_json_report
        from crp.provenance._types import ProvenanceReport

        report = ProvenanceReport(
            session_id="s", window_id="w", timestamp=0.0,
            entailment_results=[
                EntailmentResult(
                    claim_index=0, claim_text="claim",
                    fact_id="f1", label=EntailmentLabel.ENTAILED,
                    entailment_score=0.85, confidence=0.85,
                    used_model=True,
                ),
            ],
        )

        j = generate_json_report(report)
        assert "entailment" in j
        assert len(j["entailment"]) == 1
        assert j["entailment"][0]["label"] == "ENTAILED"

    def test_json_includes_risk_assessment(self):
        """JSON report should include risk assessment."""
        from crp.provenance.report_generator import generate_json_report
        from crp.provenance._types import ProvenanceReport

        report = ProvenanceReport(
            session_id="s", window_id="w", timestamp=0.0,
            risk_report=HallucinationRiskReport(
                assessments=[
                    ClaimRiskAssessment(
                        claim_index=0, claim_text="risky",
                        risk_level=HallucinationRisk.CRITICAL,
                        risk_score=0.85,
                    ),
                ],
                critical_risk_count=1,
                mean_risk_score=0.85,
                window_risk_level=HallucinationRisk.CRITICAL,
            ),
        )

        j = generate_json_report(report)
        assert "risk_assessment" in j
        assert j["risk_assessment"]["window_risk_level"] == "CRITICAL"
        assert j["risk_assessment"]["critical_risk_count"] == 1


# ===================================================================
# PART 9: ComplianceEventType Count
# ===================================================================


class TestComplianceEventTypes:
    """Verify new event types are registered."""

    def test_total_event_types(self):
        """Total ComplianceEventType count reflects all registered event groups."""
        from crp.security.audit_trail import ComplianceEventType
        # lifecycle + consent + privacy + security + oversight + session + risk +
        # LLM provenance + DPE + fidelity + entailment + hallucination +
        # provenance engine ops + RQA + activation + window DAG = 61
        assert len(ComplianceEventType) == 61

    def test_new_event_types_exist(self):
        """New entailment/risk event types should exist."""
        from crp.security.audit_trail import ComplianceEventType
        assert ComplianceEventType.ENTAILMENT_CONTRADICTION.value == "compliance.entailment_contradiction"
        assert ComplianceEventType.ENTAILMENT_VERIFIED.value == "compliance.entailment_verified"
        assert ComplianceEventType.HALLUCINATION_RISK_HIGH.value == "compliance.hallucination_risk_high"
        assert ComplianceEventType.HALLUCINATION_RISK_CRITICAL.value == "compliance.hallucination_risk_critical"
        assert ComplianceEventType.RISK_ASSESSMENT_COMPLETED.value == "compliance.risk_assessment_completed"
