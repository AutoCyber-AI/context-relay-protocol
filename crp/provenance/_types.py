# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Decision Provenance Engine — data types (§7.14.3).

Dataclasses for claim attribution, fact scoring, provenance chains,
and provenance reports used by the DPE pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

# ---------------------------------------------------------------------------
# Claim classification
# ---------------------------------------------------------------------------


class ClaimType(str, Enum):
    """Classification of individual sentences/claims in LLM output."""

    FACTUAL_CLAIM = "FACTUAL_CLAIM"     # Verifiable factual assertion
    OPINION = "OPINION"                  # Subjective view or judgment
    PROCEDURAL = "PROCEDURAL"            # Action or instruction
    HEDGE = "HEDGE"                      # Qualified/uncertain statement
    CONNECTIVE = "CONNECTIVE"            # Structural/transitional text


class AttributionType(str, Enum):
    """How a claim maps to its knowledge source."""

    CONTEXT_GROUNDED = "CONTEXT_GROUNDED"   # Supported by envelope fact(s)
    PARAMETRIC = "PARAMETRIC"               # Likely from model training data
    MIXED = "MIXED"                         # Partial context + parametric
    UNCERTAIN = "UNCERTAIN"                 # Low-confidence attribution


# ---------------------------------------------------------------------------
# Fidelity verification — did the model FAITHFULLY represent its sources?
# ---------------------------------------------------------------------------


class DistortionType(str, Enum):
    """How the model distorted a source fact in its output."""

    NUMBER_CHANGED = "NUMBER_CHANGED"           # 10% → 15%
    NEGATION_FLIP = "NEGATION_FLIP"             # "is safe" → "is not safe"
    QUALIFIER_DROPPED = "QUALIFIER_DROPPED"     # "approximately 10" → "10"
    QUALIFIER_ADDED = "QUALIFIER_ADDED"         # "10" → "always 10"
    SCOPE_CHANGED = "SCOPE_CHANGED"             # "in Q3" → "annually"
    ENTITY_SUBSTITUTED = "ENTITY_SUBSTITUTED"   # "Company A" → "Company B"
    SEMANTIC_DRIFT = "SEMANTIC_DRIFT"           # Meaning-level deviation despite lexical similarity


class FabricationType(str, Enum):
    """Category of fabricated entity in a claim."""

    NUMBER = "NUMBER"               # Invented number not in any fact
    PERCENTAGE = "PERCENTAGE"       # Invented percentage
    DATE = "DATE"                   # Invented date/year
    PROPER_NOUN = "PROPER_NOUN"     # Invented name/entity
    CITATION = "CITATION"           # Invented citation/reference


class OmissionSeverity(str, Enum):
    """How important the omitted fact was."""

    CRITICAL = "CRITICAL"       # Top-quartile relevance, omitted entirely
    HIGH = "HIGH"               # High relevance, omitted
    MEDIUM = "MEDIUM"           # Medium relevance, omitted
    LOW = "LOW"                 # Low relevance, omitted (expected)


# ---------------------------------------------------------------------------
# Scoring results
# ---------------------------------------------------------------------------


@dataclass
class FactScore:
    """Attribution score between a single claim and a single envelope fact.

    Attributes:
        fact_id: UUID of the attributed fact.
        fact_text_preview: First 120 characters of the fact text.
        semantic_similarity: Cosine similarity between claim and fact embeddings.
        lexical_overlap: N-gram token overlap ratio.
        composite_score: Weighted combination of semantic and lexical signals.
        fact_source_window: Window ID that produced the fact.
        fact_extraction_stage: Pipeline stage (1-6) that extracted the fact.
    """

    fact_id: str = ""
    fact_text_preview: str = ""         # First 120 chars of fact text
    semantic_similarity: float = 0.0    # Bag-of-words cosine similarity
    lexical_overlap: float = 0.0        # N-gram token overlap ratio
    composite_score: float = 0.0        # Weighted combination
    fact_source_window: str = ""        # Which window created this fact
    fact_extraction_stage: int = 0      # Which pipeline stage (1-6)


@dataclass
class ClaimAttribution:
    """Attribution result for a single claim in the LLM output.

    Attributes:
        claim_text: Text of the claim sentence.
        claim_index: Zero-based position of the claim in the output.
        claim_type: Classification of the claim.
        attributed_facts: Scored facts matched to this claim.
        top_score: Highest composite score among matched facts.
        attribution_type: How the claim maps to its source.
        confidence: Overall attribution confidence 0.0-1.0.
    """

    claim_text: str = ""
    claim_index: int = 0                           # Position in output (0-based)
    claim_type: ClaimType = ClaimType.CONNECTIVE
    attributed_facts: list[FactScore] = field(default_factory=list)
    top_score: float = 0.0                         # Highest composite score
    attribution_type: AttributionType = AttributionType.UNCERTAIN
    confidence: float = 0.0                        # Overall attribution confidence


# ---------------------------------------------------------------------------
# Provenance chain
# ---------------------------------------------------------------------------


@dataclass
class ProvenanceLink:
    """Single link in a provenance chain — traces from claim → source.

    Attributes:
        level: Provenance level — "claim", "fact", "window", "envelope", or "task".
        label: Human-readable label for this link.
        detail: Arbitrary key-value context for the link.
    """

    level: str = ""         # "claim", "fact", "window", "envelope", "task"
    label: str = ""         # Human-readable label for this link
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProvenanceChain:
    """Full provenance chain for one claim — linked list from output to input.

    Attributes:
        claim_text: Text of the claim being traced.
        claim_index: Position of the claim in the output.
        attribution_type: How the claim is attributed.
        links: Ordered list of provenance links from claim to task.
    """

    claim_text: str = ""
    claim_index: int = 0
    attribution_type: AttributionType = AttributionType.UNCERTAIN
    links: list[ProvenanceLink] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Provenance report
# ---------------------------------------------------------------------------


@dataclass
class ProvenanceReport:
    """Complete provenance report for a single dispatch window.

    Attributes:
        session_id: CRP session identifier.
        window_id: Dispatch window identifier.
        timestamp: Unix timestamp when the report was generated.
        total_claims: Total claims detected in the output.
        factual_claims: Number of factual claims.
        opinion_claims: Number of opinion claims.
        procedural_claims: Number of procedural claims.
        hedge_claims: Number of hedge claims.
        connective_claims: Number of connective claims.
        context_grounded_count: Claims grounded in envelope facts.
        parametric_count: Claims likely from model parametric knowledge.
        mixed_count: Claims with mixed context and parametric support.
        uncertain_count: Claims with low-confidence attribution.
        grounding_ratio: context_grounded / factual_claims.
        attributions: Per-claim attribution results.
        chains: Provenance chains for attributed claims.
        chain_verified: Whether the provenance chain passed integrity checks.
        output_token_count: Approximate output token count.
        envelope_facts_count: Number of facts packed into the envelope.
        fidelity: Fidelity verification report (distortions, fabrications, etc.).
        entailment_results: Semantic entailment verdicts.
        risk_report: Hallucination risk assessment.
        coherence: Cross-window coherence result (RQA stage 6).
        repetition: Repetition detection result (RQA stage 7).
        completeness: Completeness result (RQA stage 8).
        flow: Flow analysis result (RQA stage 9).
        rqa: Composite RQA quality score.
        amplifier_result: Regulatory amplifier result.
        quality_tier: Final quality tier after downgrade.
        redispatch: Re-dispatch decision.
    """

    session_id: str = ""
    window_id: str = ""
    timestamp: float = 0.0

    # Counts
    total_claims: int = 0
    factual_claims: int = 0
    opinion_claims: int = 0
    procedural_claims: int = 0
    hedge_claims: int = 0
    connective_claims: int = 0

    # Attribution summary
    context_grounded_count: int = 0
    parametric_count: int = 0
    mixed_count: int = 0
    uncertain_count: int = 0
    grounding_ratio: float = 0.0       # context_grounded / factual_claims

    # Payload
    attributions: list[ClaimAttribution] = field(default_factory=list)
    chains: list[ProvenanceChain] = field(default_factory=list)

    # Integrity
    chain_verified: bool = False
    output_token_count: int = 0
    envelope_facts_count: int = 0

    # Fidelity verification (None until fidelity checks run)
    fidelity: FidelityReport | None = None

    # Semantic entailment verification (None until entailment runs)
    entailment_results: list[EntailmentResult] = field(default_factory=list)

    # Hallucination risk assessment (None until risk scoring runs)
    risk_report: HallucinationRiskReport | None = None

    # Response Quality Assurance — RQA Stages 6-9 (None until RQA runs).
    # Stored as objects to avoid coupling _types to rqa_stages at import time.
    coherence: object | None = None      # Stage 6 — CoherenceResult
    repetition: object | None = None     # Stage 7 — RepetitionResult
    completeness: object | None = None   # Stage 8 — CompletenessResult
    flow: object | None = None           # Stage 9 — FlowResult
    rqa: object | None = None            # RQAResult (composite quality score)
    amplifier_result: object | None = None  # AmplifierResult (regulatory)
    quality_tier: str = ""               # emitted CRP-Context-Quality-Tier (post-downgrade)
    redispatch: object | None = None     # RedispatchDecision


# ---------------------------------------------------------------------------
# Fidelity verification results
# ---------------------------------------------------------------------------


@dataclass
class DistortionResult:
    """A specific distortion found between a grounded claim and its source fact.

    Attributes:
        claim_index: Position of the claim in the output.
        claim_text: Text of the distorted claim.
        source_fact_id: ID of the source fact.
        source_fact_preview: Preview of the source fact.
        distortion_type: Category of distortion.
        severity: Severity score 0.0-1.0.
        detail: Human-readable explanation.
        claim_value: Value as stated in the claim.
        fact_value: Value as stated in the source fact.
    """

    claim_index: int = 0
    claim_text: str = ""
    source_fact_id: str = ""
    source_fact_preview: str = ""
    distortion_type: DistortionType = DistortionType.NUMBER_CHANGED
    severity: float = 0.0          # 0.0-1.0
    detail: str = ""               # Human-readable explanation
    claim_value: str = ""          # The value in the claim
    fact_value: str = ""           # The value in the source fact


@dataclass
class FabricationResult:
    """A specific fabrication found in a claim — an entity not in any source fact.

    Attributes:
        claim_index: Position of the claim in the output.
        claim_text: Text of the claim containing the fabrication.
        fabricated_entity: Invented entity text.
        entity_type: Category of fabricated entity.
        severity: Severity score 0.0-1.0.
        detail: Human-readable explanation.
    """

    claim_index: int = 0
    claim_text: str = ""
    fabricated_entity: str = ""
    entity_type: FabricationType = FabricationType.NUMBER
    severity: float = 0.0         # 0.0-1.0
    detail: str = ""


@dataclass
class OmissionResult:
    """An envelope fact that the model ignored entirely.

    Attributes:
        fact_id: ID of the omitted fact.
        fact_text_preview: Preview of the omitted fact.
        fact_relevance_score: Original packing relevance score.
        max_attribution_score: Highest score any claim gave this fact.
        severity: Importance of the omission.
    """

    fact_id: str = ""
    fact_text_preview: str = ""
    fact_relevance_score: float = 0.0    # Original packing score
    max_attribution_score: float = 0.0   # Highest score any claim gave this fact
    severity: OmissionSeverity = OmissionSeverity.LOW


@dataclass
class ContradictionResult:
    """Two claims that contradict each other.

    Attributes:
        claim_a_index: Position of the first claim.
        claim_a_text: Text of the first claim.
        claim_b_index: Position of the second claim.
        claim_b_text: Text of the second claim.
        contradiction_type: Category of contradiction.
        severity: Severity score 0.0-1.0.
        detail: Human-readable explanation.
    """

    claim_a_index: int = 0
    claim_a_text: str = ""
    claim_b_index: int = 0
    claim_b_text: str = ""
    contradiction_type: str = ""     # "NEGATION" | "NUMBER_CONFLICT" | "SEMANTIC"
    severity: float = 0.0           # 0.0-1.0
    detail: str = ""


@dataclass
class FidelityReport:
    """Complete fidelity verification results for a dispatch window.

    Answers: "Given source attribution, did the model faithfully represent
    the sources, or did it distort, fabricate, omit, or contradict?"
    """

    distortions: list[DistortionResult] = field(default_factory=list)
    fabrications: list[FabricationResult] = field(default_factory=list)
    omissions: list[OmissionResult] = field(default_factory=list)
    contradictions: list[ContradictionResult] = field(default_factory=list)

    # Aggregate counts
    distortion_count: int = 0
    fabrication_count: int = 0
    critical_omission_count: int = 0
    contradiction_count: int = 0

    # Composite fidelity score (1.0 = perfect fidelity, 0.0 = severe issues)
    fidelity_score: float = 1.0


# ---------------------------------------------------------------------------
# Semantic Entailment — ML-powered claim↔fact verification
# ---------------------------------------------------------------------------


class EntailmentLabel(str, Enum):
    """NLI classification of a claim against its source fact."""

    ENTAILED = "ENTAILED"               # Claim logically follows from fact
    CONTRADICTION = "CONTRADICTION"     # Claim contradicts the fact
    NEUTRAL = "NEUTRAL"                 # Claim is unrelated to the fact


@dataclass
class EntailmentResult:
    """Semantic entailment verdict for a single claim↔fact pair.

    Uses Natural Language Inference (NLI) to determine whether a claim
    is *semantically* supported by its attributed source fact — beyond
    lexical overlap.
    """

    claim_index: int = 0
    claim_text: str = ""
    fact_id: str = ""
    fact_text_preview: str = ""
    label: EntailmentLabel = EntailmentLabel.NEUTRAL
    confidence: float = 0.0            # P(predicted_label)
    entailment_score: float = 0.0      # P(entailed)
    contradiction_score: float = 0.0   # P(contradiction)
    neutral_score: float = 0.0         # P(neutral)
    used_model: bool = False           # True if NLI model ran; False if heuristic


# ---------------------------------------------------------------------------
# Hallucination Risk — composite per-claim risk assessment
# ---------------------------------------------------------------------------


class HallucinationRisk(str, Enum):
    """Per-claim hallucination risk level."""

    LOW = "LOW"                 # Well-sourced, semantically faithful
    MEDIUM = "MEDIUM"           # Partially sourced or minor fidelity issues
    HIGH = "HIGH"               # Poorly sourced or semantic mismatch
    CRITICAL = "CRITICAL"       # Contradicts source or fabricated content


@dataclass
class ClaimRiskAssessment:
    """Hallucination risk assessment for a single claim.

    Aggregates four independent signals into one auditable risk score:
      1. Attribution signal — how well-sourced is this claim?
      2. Fidelity signal — did lexical checks find distortions?
      3. Entailment signal — does NLI confirm semantic support?
      4. Specificity signal — how specific (and thus risky) is the claim?

    Attributes:
        claim_index: Position of the claim in the output.
        claim_text: Text of the assessed claim.
        risk_level: Discrete risk level.
        risk_score: Continuous risk score 0.0-1.0 (1.0 = critical).
        attribution_signal: Well-sourcedness signal 0.0-1.0.
        fidelity_signal: Lexical fidelity signal 0.0-1.0.
        entailment_signal: Semantic entailment signal 0.0-1.0.
        specificity_signal: Specificity signal 0.0-1.0.
        risk_factors: Human-readable list of risk factors.
    """

    claim_index: int = 0
    claim_text: str = ""
    risk_level: HallucinationRisk = HallucinationRisk.LOW
    risk_score: float = 0.0            # 0.0=safe, 1.0=critical
    # Individual signals (all 0.0-1.0; higher = safer)
    attribution_signal: float = 0.0
    fidelity_signal: float = 1.0
    entailment_signal: float = 0.0
    specificity_signal: float = 0.0    # Higher = more specific = riskier
    risk_factors: list[str] = field(default_factory=list)


@dataclass
class HallucinationRiskReport:
    """Window-level hallucination risk report.

    Answers: \"For each claim, how likely is it that the model hallucinated,
    and what is the overall risk profile of this output?\"
    """

    assessments: list[ClaimRiskAssessment] = field(default_factory=list)
    high_risk_count: int = 0
    critical_risk_count: int = 0
    mean_risk_score: float = 0.0
    window_risk_level: HallucinationRisk = HallucinationRisk.LOW


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass
class ProvenanceConfig:
    """Configuration for the Decision Provenance Engine.

    Attributes:
        enabled: Master switch for the entire DPE pipeline.
        min_claim_length: Minimum claim text length to analyse.
        max_claims_per_output: Maximum claims to process per window.
        similarity_threshold: Score below which attribution is PARAMETRIC.
        mixed_threshold: Boundary between MIXED and PARAMETRIC attribution.
        min_grounding_semantic: Minimum semantic score for grounding.
        min_grounding_lexical: Minimum lexical score for grounding.
        min_mixed_semantic: Minimum semantic score for mixed attribution.
        lexical_weight: Weight applied to lexical overlap.
        semantic_weight: Weight applied to semantic similarity.
        generate_report: Whether to emit a structured report.
        fact_preview_length: Characters of fact text included in previews.
        entailment_enabled: Whether to run semantic entailment verification.
        entailment_model: HuggingFace model id for entailment (if available).
        entailment_contradiction_threshold: P(contradiction) threshold for flagging.
        risk_scoring_enabled: Whether to compute hallucination risk scores.
        risk_weight_attribution: Weight of attribution signal in risk score.
        risk_weight_fidelity: Weight of fidelity signal in risk score.
        risk_weight_entailment: Weight of entailment signal in risk score.
        risk_weight_specificity: Weight of specificity signal in risk score.
        amplifiers_enabled: Whether regulatory amplifiers are active.
        amplifier_gdpr_pii: Multiplier when GDPR PII is present.
        amplifier_eu_ai_act_high: Multiplier for high-risk EU AI Act systems.
        amplifier_sector: Multiplier for financial/medical domains.
        amplifier_agent_depth: Multiplier for deep agent loops.
        amplifier_cross_window: Multiplier for cross-window contradictions.
        amplifier_severe_repetition: Multiplier for severe repetition.
        rqa_enabled: Whether RQA stages 6-9 run.
        rqa_weight_repetition: Weight of repetition in composite quality score.
        rqa_weight_completeness: Weight of completeness in composite quality score.
        rqa_weight_flow: Weight of flow in composite quality score.
        rqa_weight_coherence: Weight of coherence in composite quality score.
    """

    enabled: bool = True

    # Claim detection
    min_claim_length: int = 10          # Skip very short fragments
    max_claims_per_output: int = 50     # Safety limit

    # Attribution scoring
    similarity_threshold: float = 0.50  # Below this → PARAMETRIC
    mixed_threshold: float = 0.35       # Between mixed and parametric
    # Minimum per-signal scores required before trusting attribution. These
    # prevent a claim from being "grounded" purely by embedding similarity to
    # an unrelated fact (the loaded-CKF hallucination masking problem).
    min_grounding_semantic: float = 0.0
    min_grounding_lexical: float = 0.0
    min_mixed_semantic: float = 0.0
    lexical_weight: float = 0.40        # Weight for lexical overlap
    semantic_weight: float = 0.60       # Weight for semantic similarity

    # Report generation
    generate_report: bool = True
    fact_preview_length: int = 120      # Chars of fact text in previews

    # Semantic entailment
    entailment_enabled: bool = True
    entailment_model: str = "cross-encoder/nli-MiniLM2-L6-H768"
    entailment_contradiction_threshold: float = 0.70  # P(contradiction) above this → flag

    # Hallucination risk scoring
    risk_scoring_enabled: bool = True
    risk_weight_attribution: float = 0.30
    risk_weight_fidelity: float = 0.25
    risk_weight_entailment: float = 0.30
    risk_weight_specificity: float = 0.15

    # Regulatory amplifiers (CRP-SPEC-005 §17) — multiply the composite score
    # when the regulatory context raises the stakes. Composite is capped at 1.0.
    amplifiers_enabled: bool = True
    amplifier_gdpr_pii: float = 1.30
    amplifier_eu_ai_act_high: float = 1.25
    amplifier_sector: float = 1.20          # financial or medical domain
    amplifier_agent_depth: float = 1.15     # CRP-Agent-Loop-Depth > 2
    amplifier_cross_window: float = 1.20    # cross-window contradiction
    amplifier_severe_repetition: float = 1.10

    # RQA composite quality score (CRP-SPEC-005 §18) — distinct from the safety
    # risk score; measures usefulness, not truthfulness.
    rqa_enabled: bool = True
    rqa_weight_repetition: float = 0.25
    rqa_weight_completeness: float = 0.35
    rqa_weight_flow: float = 0.25
    rqa_weight_coherence: float = 0.15
