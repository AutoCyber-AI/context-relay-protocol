# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Hallucination Risk Scorer — per-claim composite risk assessment (§7.14.3).

**WHY THIS EXISTS**

An auditor reviewing AI output asks ONE question:

    "How likely is it that THIS claim is a hallucination?"

Currently they must mentally fuse:
  - Attribution score (was it grounded?)
  - Fidelity score (was the source distorted?)
  - Entailment verdict (does NLI confirm semantic support?)
  - Claim specificity (is this a precise claim that's dangerous if wrong?)

This module fuses those four signals into ONE auditable risk score per
claim, with a clear risk level (LOW / MEDIUM / HIGH / CRITICAL) and a
list of human-readable risk factors explaining WHY.

**RISK FORMULA**

    risk = 1.0 - (w_a * attribution + w_f * fidelity + w_e * entailment + w_s * (1 - specificity))

Where:
  - attribution: top_score from DPE (0-1, higher = better sourced)
  - fidelity: 1.0 if no distortions/fabrications for this claim, else degraded
  - entailment: P(ENTAILED) from NLI (0-1, higher = semantically confirmed)
  - specificity: density of specific entities in the claim (higher = riskier)
  - w_a, w_f, w_e, w_s: configurable weights (default 0.30, 0.25, 0.30, 0.15)

Risk levels:
  - risk < 0.25 → LOW
  - risk < 0.50 → MEDIUM
  - risk < 0.75 → HIGH
  - risk ≥ 0.75 → CRITICAL
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from ._types import (
    AttributionType,
    ClaimAttribution,
    ClaimRiskAssessment,
    ClaimType,
    DistortionResult,
    EntailmentLabel,
    EntailmentResult,
    FabricationResult,
    FidelityReport,
    HallucinationRisk,
    HallucinationRiskReport,
    ProvenanceConfig,
)

# ---------------------------------------------------------------------------
# Claim specificity analysis
# ---------------------------------------------------------------------------

# Specific entities that make a claim "risky if wrong"
_NUMBER_RE = re.compile(r"\b\d[\d,]*(?:\.\d+)?\s*%?\b")
_DATE_RE = re.compile(
    r"\b(?:(?:19|20)\d{2}|Q[1-4]\s+\d{4}|"
    r"(?:January|February|March|April|May|June|July|August|"
    r"September|October|November|December)\s+\d{4})\b",
    re.IGNORECASE,
)
_PROPER_NOUN_RE = re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b")
_MEASUREMENT_RE = re.compile(
    r"\b\d+(?:\.\d+)?\s*(?:mg|kg|ml|cm|mm|km|lb|oz|GB|MB|TB|ms|MHz|GHz)\b",
    re.IGNORECASE,
)


def compute_specificity(claim_text: str) -> float:
    """Compute how specific a claim is (0.0=vague, 1.0=highly specific).

    More specific claims are riskier if unsupported — "Revenue grew 23.4%
    in Q3 2024 according to Deloitte" is far more dangerous wrong than
    "Performance improved."

    Specificity = min(1.0, entity_count / 5) — normalised density of
    numbers, dates, proper nouns, and measurements.
    """
    entities = 0
    entities += len(_NUMBER_RE.findall(claim_text))
    entities += len(_DATE_RE.findall(claim_text))
    entities += len(_PROPER_NOUN_RE.findall(claim_text))
    entities += len(_MEASUREMENT_RE.findall(claim_text))
    return min(1.0, entities / 5.0)


# ---------------------------------------------------------------------------
# Per-claim fidelity signal
# ---------------------------------------------------------------------------


def _claim_fidelity_signal(
    claim_index: int,
    fidelity: FidelityReport | None,
) -> tuple[float, list[str]]:
    """Compute fidelity signal for a single claim.

    Returns (fidelity_score, risk_factors) where:
      - 1.0 = no issues found
      - <1.0 = distortions or fabrications detected
    """
    if fidelity is None:
        return 1.0, []

    score = 1.0
    factors: list[str] = []

    for d in fidelity.distortions:
        if d.claim_index == claim_index:
            score -= 0.20
            factors.append(f"Distortion: {d.distortion_type.value} (sev={d.severity:.2f})")

    for f in fidelity.fabrications:
        if f.claim_index == claim_index:
            score -= 0.15
            factors.append(f"Fabrication: {f.entity_type.value} '{f.fabricated_entity}'")

    return max(0.0, score), factors


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def score_hallucination_risk(
    attributions: list[ClaimAttribution],
    *,
    fidelity: FidelityReport | None = None,
    entailment_results: list[EntailmentResult] | None = None,
    config: ProvenanceConfig | None = None,
) -> HallucinationRiskReport:
    """Score hallucination risk for every claim in the output.

    Combines four independent signals per claim:
      1. **Attribution** — how well-sourced is the claim?
      2. **Fidelity** — did lexical checks find distortions?
      3. **Entailment** — does NLI confirm semantic support?
      4. **Specificity** — how specific (and thus risky) is the claim?

    Args:
        attributions: Scored claim attributions from the DPE pipeline.
        fidelity: FidelityReport from the fidelity verification layer.
        entailment_results: EntailmentResults from the entailment verifier.
        config: ProvenanceConfig with risk weight configuration.

    Returns:
        HallucinationRiskReport with per-claim assessments and aggregates.
    """
    cfg = config or ProvenanceConfig()
    if not cfg.risk_scoring_enabled:
        return HallucinationRiskReport()

    # Build entailment lookup by claim_index
    ent_lookup: dict[int, EntailmentResult] = {}
    if entailment_results:
        for er in entailment_results:
            ent_lookup[er.claim_index] = er

    assessments: list[ClaimRiskAssessment] = []

    for attr in attributions:
        # Only score factual and hedge claims (the risky ones)
        if attr.claim_type not in (ClaimType.FACTUAL_CLAIM, ClaimType.HEDGE):
            assessments.append(ClaimRiskAssessment(
                claim_index=attr.claim_index,
                claim_text=attr.claim_text[:200],
                risk_level=HallucinationRisk.LOW,
                risk_score=0.0,
                risk_factors=["Non-factual claim — low inherent risk"],
            ))
            continue

        risk_factors: list[str] = []

        # --- Signal 1: Attribution (higher = safer) ---
        attribution_signal = attr.top_score
        if attr.attribution_type == AttributionType.PARAMETRIC:
            attribution_signal = max(0.0, attribution_signal - 0.30)
            risk_factors.append("Parametric knowledge — not grounded in context")
        elif attr.attribution_type == AttributionType.UNCERTAIN:
            attribution_signal = 0.0
            risk_factors.append("Uncertain attribution — source unknown")
        elif attr.attribution_type == AttributionType.MIXED:
            # Proportional credit: a claim just above mixed_threshold gets
            # almost no grounding credit; full credit only near similarity_threshold.
            span = max(cfg.similarity_threshold - cfg.mixed_threshold, 1e-9)
            attribution_signal = max(0.0, min(1.0, (attr.top_score - cfg.mixed_threshold) / span))
            risk_factors.append("Mixed attribution — partially parametric")

        # --- Signal 2: Fidelity (higher = safer) ---
        fidelity_signal, fidelity_factors = _claim_fidelity_signal(
            attr.claim_index, fidelity,
        )
        risk_factors.extend(fidelity_factors)

        # --- Signal 3: Specificity (higher = riskier) ---
        specificity = compute_specificity(attr.claim_text)
        if specificity > 0.6:
            risk_factors.append(f"Highly specific claim (specificity={specificity:.2f})")

        # --- Signal 4: Entailment (higher = safer) ---
        ent = ent_lookup.get(attr.claim_index)
        if ent is not None:
            entailment_signal = ent.entailment_score
            if ent.label == EntailmentLabel.CONTRADICTION:
                entailment_signal = 0.0
                risk_factors.append(
                    f"NLI CONTRADICTION (P={ent.contradiction_score:.2f}) — "
                    f"claim semantically conflicts with source fact"
                )
            elif ent.label == EntailmentLabel.NEUTRAL:
                entailment_signal = 0.3  # Partial credit for neutral
                risk_factors.append("NLI neutral — claim not semantically supported")
            # Heuristic entailment is not enough for highly specific claims;
            # without a real NLI model, semantic similarity can falsely confirm
            # fabricated numbers/names/dates that happen to match a topic.
            if not ent.used_model and specificity > 0.5:
                entailment_signal = min(entailment_signal, 0.30)
                risk_factors.append("Heuristic entailment capped for specific claim")
        else:
            # No entailment data — use attribution as proxy
            entailment_signal = attribution_signal * 0.5

        # --- Composite risk score ---
        # Safety score = weighted combination of clean signals
        #
        # WEIGHT RATIONALE (G-3):
        # - attribution (0.30): Primary grounding signal — whether the claim
        #   can be traced to envelope facts. Highest weight because
        #   ungrounded claims are the root cause of hallucinations.
        # - entailment (0.30): Equal to attribution because semantic
        #   verification catches meaning-level drift that attribution
        #   scoring alone cannot (e.g., specificity loss, causation
        #   inflation). Provides the ML-powered "second opinion".
        # - fidelity (0.25): Lexical verification layer — catches number
        #   changes, negation flips, qualifier drops. Slightly lower
        #   weight because it's surface-level and the entailment layer
        #   provides deeper semantic coverage.
        # - specificity (0.15): Risk amplifier — highly specific claims
        #   (numbers, dates, names) are more dangerous if wrong, but
        #   specificity alone doesn't indicate hallucination.
        #
        safety = (
            cfg.risk_weight_attribution * attribution_signal
            + cfg.risk_weight_fidelity * fidelity_signal
            + cfg.risk_weight_entailment * entailment_signal
            + cfg.risk_weight_specificity * (1.0 - specificity)
        )
        risk_score = round(max(0.0, min(1.0, 1.0 - safety)), 4)

        # CRITICAL SIGNAL OVERRIDE (G-3):
        # If ANY key signal is catastrophically low (< 0.15), override
        # risk to at least HIGH.  A single collapsed signal means the
        # claim has a fundamental grounding/fidelity/semantic gap that
        # the weighted average might mask.
        _CRITICAL_FLOOR = 0.15
        critical_signals = [
            ("attribution", attribution_signal),
            ("fidelity", fidelity_signal),
            ("entailment", entailment_signal),
        ]
        for signal_name, signal_val in critical_signals:
            if signal_val < _CRITICAL_FLOOR:
                risk_score = max(risk_score, 0.50)  # Floor = HIGH
                risk_factors.append(
                    f"Critical signal override: {signal_name}={signal_val:.2f} < {_CRITICAL_FLOOR}"
                )
                break

        # --- Risk level ---
        if risk_score >= 0.75:
            risk_level = HallucinationRisk.CRITICAL
        elif risk_score >= 0.50:
            risk_level = HallucinationRisk.HIGH
        elif risk_score >= 0.25:
            risk_level = HallucinationRisk.MEDIUM
        else:
            risk_level = HallucinationRisk.LOW

        assessments.append(ClaimRiskAssessment(
            claim_index=attr.claim_index,
            claim_text=attr.claim_text[:200],
            risk_level=risk_level,
            risk_score=risk_score,
            attribution_signal=round(attribution_signal, 4),
            fidelity_signal=round(fidelity_signal, 4),
            entailment_signal=round(entailment_signal, 4),
            specificity_signal=round(specificity, 4),
            risk_factors=risk_factors if risk_factors else ["No risk factors identified"],
        ))

    # --- Window-level aggregates ---
    high_count = sum(1 for a in assessments if a.risk_level == HallucinationRisk.HIGH)
    critical_count = sum(1 for a in assessments if a.risk_level == HallucinationRisk.CRITICAL)

    factual_assessments = [
        a for a in assessments if a.risk_score > 0.0
    ]
    mean_risk = (
        sum(a.risk_score for a in factual_assessments) / len(factual_assessments)
        if factual_assessments else 0.0
    )

    if critical_count > 0:
        window_level = HallucinationRisk.CRITICAL
    elif high_count > 0:
        window_level = HallucinationRisk.HIGH
    elif mean_risk >= 0.25:
        window_level = HallucinationRisk.MEDIUM
    else:
        window_level = HallucinationRisk.LOW

    return HallucinationRiskReport(
        assessments=assessments,
        high_risk_count=high_count,
        critical_risk_count=critical_count,
        mean_risk_score=round(mean_risk, 4),
        window_risk_level=window_level,
    )
