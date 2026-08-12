# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Post-extraction quality gate — 3-tier validation (§3.2 2H).

Tier 1: Structural validation (schema, parse success, empty facts).
Tier 2: Confidence threshold filter (flag low-confidence facts).
Tier 3: Anomaly detection (fact explosion, zero facts, duplicates).
"""

from __future__ import annotations

import logging
import statistics
from typing import Any

from crp.extraction.types import (
    ExtractionResult,
    Fact,
    ValidationIssue,
    ValidationResult,
    ValidationSeverity,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tier 1 — Structural Validation
# ---------------------------------------------------------------------------

def structural_validation(
    result: ExtractionResult,
    output_schema: dict[str, Any] | None = None,
) -> ValidationResult:
    """Check schema compliance, parse success rate, and empty facts."""
    issues: list[ValidationIssue] = []

    # Check 1: JSON Schema compliance (if output_schema provided)
    if output_schema:
        try:
            import jsonschema  # type: ignore[import-untyped]

            payload = [{"text": f.text, "category": f.category} for f in result.facts]
            jsonschema.validate(payload, output_schema)
        except ImportError:
            pass  # jsonschema optional
        except Exception as exc:
            issues.append(ValidationIssue(
                type="SCHEMA_MISMATCH",
                severity=ValidationSeverity.HIGH,
                detail=str(exc)[:200],
            ))

    # Check 2: Parsing success rate — count facts with very short text
    parse_failures = sum(1 for f in result.facts if not f.text.strip())
    if result.total_facts > 0 and parse_failures > 0.1 * result.total_facts:
        issues.append(ValidationIssue(
            type="HIGH_PARSE_FAILURE_RATE",
            severity=ValidationSeverity.MEDIUM,
            detail=f"{parse_failures} facts could not be parsed",
        ))

    # Check 3: Suspiciously short facts
    empty = [f for f in result.facts if len(f.text.strip()) < 5]
    if empty:
        issues.append(ValidationIssue(
            type="EMPTY_FACTS",
            severity=ValidationSeverity.LOW,
            detail=f"{len(empty)} facts are suspiciously short (<5 chars)",
        ))

    passed = all(i.severity != ValidationSeverity.HIGH for i in issues)
    return ValidationResult(tier=1, passed=passed, issues=issues)


# ---------------------------------------------------------------------------
# Tier 2 — Confidence Threshold
# ---------------------------------------------------------------------------

def confidence_threshold_filter(
    result: ExtractionResult,
    floor: float = 0.6,
) -> ValidationResult:
    """Mark facts below the confidence floor as flagged.

    Low-confidence facts are NOT excluded — they remain but get a
    0.5× score multiplier in envelope packing.
    """
    flagged = 0
    for fact in result.facts:
        if fact.confidence < floor:
            fact.flagged_confidence = True
            fact.confidence_flag_reason = f"Below baseline {floor:.2f}"
            flagged += 1

    issues: list[ValidationIssue] = []
    if flagged:
        issues.append(ValidationIssue(
            type="LOW_CONFIDENCE_FACTS",
            severity=ValidationSeverity.LOW,
            detail=f"{flagged} facts below confidence floor {floor:.2f}",
        ))
    return ValidationResult(tier=2, passed=True, issues=issues)


# ---------------------------------------------------------------------------
# Tier 3 — Anomaly Detection
# ---------------------------------------------------------------------------

def anomaly_detection(
    result: ExtractionResult,
    history: list[ExtractionResult] | None = None,
) -> ValidationResult:
    """Check for fact-count explosion, zero facts, and duplicates."""
    issues: list[ValidationIssue] = []

    # Check 1: Fact count explosion (>5× typical)
    if history and len(history) >= 2:
        typical = statistics.mean([r.total_facts for r in history[-5:]])
        if typical > 0 and result.total_facts > 5 * typical:
            issues.append(ValidationIssue(
                type="UNUSUALLY_HIGH_FACT_COUNT",
                severity=ValidationSeverity.MEDIUM,
                detail=(
                    f"{result.total_facts} facts vs typical ~{typical:.0f}. "
                    "Possible extraction running on stack trace?"
                ),
            ))

    # Check 2: Zero facts
    if result.total_facts == 0:
        issues.append(ValidationIssue(
            type="NO_FACTS_EXTRACTED",
            severity=ValidationSeverity.MEDIUM,
            detail="Zero facts extracted — content may be too short or unstructured",
        ))

    # Check 3: >20% duplicates
    hashes = [hash(f.text) for f in result.facts]
    duplicates = len(hashes) - len(set(hashes))
    if result.total_facts > 0 and duplicates > 0.2 * result.total_facts:
        issues.append(ValidationIssue(
            type="EXCESSIVE_NEAR_DUPLICATES",
            severity=ValidationSeverity.LOW,
            detail=f"{duplicates} near-duplicate facts detected",
        ))

    passed = all(i.severity != ValidationSeverity.HIGH for i in issues)
    return ValidationResult(tier=3, passed=passed, issues=issues)


# ---------------------------------------------------------------------------
# Fact normalisation
# ---------------------------------------------------------------------------

def normalize_facts(facts: list[Fact], max_tokens: int = 100, min_tokens: int = 5) -> list[Fact]:
    """Split overly long facts and merge very short ones.

    Uses word count as a proxy for token count (accurate tokenisation is Phase 4).
    """
    normalized: list[Fact] = []
    short_buffer: list[Fact] = []

    for fact in facts:
        words = fact.text.split()
        wc = len(words)

        if wc > max_tokens:
            # Split into chunks of ~max_tokens words
            for i in range(0, wc, max_tokens):
                chunk = " ".join(words[i : i + max_tokens])
                normalized.append(Fact(
                    text=chunk,
                    category=fact.category,
                    source_window_id=fact.source_window_id,
                    confidence=fact.confidence,
                    extraction_stage=fact.extraction_stage,
                    metadata={**fact.metadata, "split_from": fact.id},
                ))
        elif wc < min_tokens:
            short_buffer.append(fact)
            if len(short_buffer) >= 3:
                merged_text = " | ".join(f.text for f in short_buffer)
                normalized.append(Fact(
                    text=merged_text,
                    category=short_buffer[0].category,
                    source_window_id=short_buffer[0].source_window_id,
                    confidence=min(f.confidence for f in short_buffer),
                    extraction_stage=short_buffer[0].extraction_stage,
                    metadata={"merged_from": [f.id for f in short_buffer]},
                ))
                short_buffer.clear()
        else:
            normalized.append(fact)

    # Flush remaining short facts
    normalized.extend(short_buffer)
    return normalized


# ---------------------------------------------------------------------------
# Composite quality gate
# ---------------------------------------------------------------------------

def run_quality_gate(
    result: ExtractionResult,
    *,
    output_schema: dict[str, Any] | None = None,
    confidence_floor: float = 0.6,
    history: list[ExtractionResult] | None = None,
) -> ExtractionResult:
    """Run all 3 quality-gate tiers and update the ExtractionResult in-place."""
    all_issues: list[str] = []

    # Tier 1
    v1 = structural_validation(result, output_schema)
    if not v1.passed:
        result.quality_gate_passed = False
    all_issues.extend(f"[T1] {i.type}: {i.detail}" for i in v1.issues)

    # Tier 2
    v2 = confidence_threshold_filter(result, confidence_floor)
    all_issues.extend(f"[T2] {i.type}: {i.detail}" for i in v2.issues)

    # Tier 3
    v3 = anomaly_detection(result, history)
    if not v3.passed:
        result.quality_gate_passed = False
    all_issues.extend(f"[T3] {i.type}: {i.detail}" for i in v3.issues)

    result.quality_issues = all_issues

    # Normalise facts
    result.facts = normalize_facts(result.facts)
    result.facts_after_normalization = len(result.facts)

    return result
