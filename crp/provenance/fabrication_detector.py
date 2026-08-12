# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Fabrication Detector — catch invented entities not in any source fact.

The model outputs "According to the 2024 Johnson report, revenue grew
23%."  The envelope contains no entity "Johnson", no year "2024", no
number "23".  The model fabricated a citation to sound authoritative.

This module extracts specific entities from claims (numbers, percentages,
dates, proper nouns, citations) and cross-references them against ALL
envelope facts.  Entities found in no source are flagged as fabrications.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from crp.envelope.packer import PackedFact

from ._types import (
    AttributionType,
    ClaimAttribution,
    ClaimType,
    FabricationResult,
    FabricationType,
)


# ---------------------------------------------------------------------------
# Entity extraction patterns
# ---------------------------------------------------------------------------

# Percentages: "15%", "3.2%", "0.5 %"
_PCT_RE = re.compile(r"\b(\d+(?:\.\d+)?)\s*%")

# Numbers with context (skip very small/common numbers 0-9):
# "$1.2M", "1,234", "45.6", but not "a", "the", single digits
_NUM_RE = re.compile(r"(?<![a-zA-Z])(\d[\d,]*(?:\.\d+)?)")

# Dates: "2024", "2023-01-15", "January 2024", "Q3 2023"
_DATE_RE = re.compile(
    r"\b("
    r"(?:19|20)\d{2}(?:-\d{2}(?:-\d{2})?)?"           # 2024, 2024-01-15
    r"|(?:January|February|March|April|May|June"
    r"|July|August|September|October|November|December)"
    r"\s+(?:19|20)\d{2}"                                # January 2024
    r"|Q[1-4]\s+(?:19|20)\d{2}"                         # Q3 2023
    r")\b"
)

# Proper nouns: 2+ capitalized words in sequence
_PROPER_RE = re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b")

# Citation-like: "according to X", "X et al.", "the X report/study/paper"
_CITATION_RE = re.compile(
    r"(?:"
    r"according\s+to\s+([A-Z][\w\s]+?)(?:\s*,|\s+\(|\s+report)"
    r"|\b([A-Z][a-z]+\s+et\s+al\.?)"
    r"|the\s+([A-Z][\w\s]+?)\s+(?:report|study|paper|analysis|survey)"
    r")",
    re.IGNORECASE,
)

# Trivial numbers to skip (too common to be meaningful)
_TRIVIAL_NUMBERS = frozenset({
    "0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10",
    "100", "1000",
})


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _entity_in_facts(entity: str, fact_texts: Sequence[str]) -> bool:
    """Check if entity appears in any fact using word-boundary matching.

    Uses per-fact matching (not a single concatenated corpus) to avoid
    false negatives where entity fragments span fact boundaries.
    Uses regex word-boundary matching to avoid substring false positives
    (e.g., "23" matching inside "1234").
    """
    # Escape the entity for safe regex use, then match with word boundaries
    pattern = re.compile(
        r"(?<!\d)" + re.escape(entity.lower()) + r"(?!\d)"
        if entity.strip().replace(".", "").replace(",", "").isdigit()
        else r"\b" + re.escape(entity.lower()) + r"\b",
        re.IGNORECASE,
    )
    return any(pattern.search(fact) for fact in fact_texts)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def detect_fabrications(
    attributions: list[ClaimAttribution],
    packed_facts: Sequence[PackedFact],
) -> list[FabricationResult]:
    """Detect fabricated entities in claims that appear in no source fact.

    Examines FACTUAL_CLAIM and HEDGE claims for specific entities (numbers,
    percentages, dates, proper nouns, citations) and flags those not found
    in any envelope fact.

    Args:
        attributions: Scored claim attributions.
        packed_facts: All envelope facts.

    Returns:
        List of FabricationResult — one per fabricated entity found.
    """
    if not packed_facts:
        # No facts to check against — every specific entity is unsourced
        # but we can't meaningfully flag without reference material
        return []

    # Pre-compute lowercased per-fact texts for boundary matching
    fact_texts = [pf.text.lower() for pf in packed_facts]
    results: list[FabricationResult] = []

    for attr in attributions:
        # Only check factual and hedge claims
        if attr.claim_type not in (ClaimType.FACTUAL_CLAIM, ClaimType.HEDGE):
            continue
        # Fabrication only matters when the model presents the claim as grounded
        # in the supplied context. Parametric/uncertain claims are expected to draw
        # on general knowledge, so unsourced entities there are not treated as
        # fabrications.
        if attr.attribution_type not in (AttributionType.CONTEXT_GROUNDED, AttributionType.MIXED):
            continue

        claim = attr.claim_text

        # --- Check 1: Percentages ---
        for m in _PCT_RE.finditer(claim):
            pct_str = m.group(0)  # e.g., "15%"
            if not _entity_in_facts(m.group(1), fact_texts):
                results.append(FabricationResult(
                    claim_index=attr.claim_index,
                    claim_text=claim[:200],
                    fabricated_entity=pct_str,
                    entity_type=FabricationType.PERCENTAGE,
                    severity=0.80,
                    detail=f"Percentage '{pct_str}' not found in any source fact",
                ))

        # --- Check 2: Significant numbers (> 9) ---
        for m in _NUM_RE.finditer(claim):
            num_raw = m.group(1).replace(",", "")
            if num_raw in _TRIVIAL_NUMBERS:
                continue
            # Skip if it's part of a percentage (already caught above)
            end_pos = m.end()
            if end_pos < len(claim) and claim[end_pos:end_pos + 1] == "%":
                continue
            if not _entity_in_facts(num_raw, fact_texts):
                results.append(FabricationResult(
                    claim_index=attr.claim_index,
                    claim_text=claim[:200],
                    fabricated_entity=num_raw,
                    entity_type=FabricationType.NUMBER,
                    severity=0.70,
                    detail=f"Number '{num_raw}' not found in any source fact",
                ))

        # --- Check 3: Dates ---
        for m in _DATE_RE.finditer(claim):
            date_str = m.group(0)
            if not _entity_in_facts(date_str, fact_texts):
                results.append(FabricationResult(
                    claim_index=attr.claim_index,
                    claim_text=claim[:200],
                    fabricated_entity=date_str,
                    entity_type=FabricationType.DATE,
                    severity=0.75,
                    detail=f"Date '{date_str}' not found in any source fact",
                ))

        # --- Check 4: Citations ---
        for m in _CITATION_RE.finditer(claim):
            citation = m.group(1) or m.group(2) or m.group(3)
            if citation and not _entity_in_facts(citation.strip(), fact_texts):
                results.append(FabricationResult(
                    claim_index=attr.claim_index,
                    claim_text=claim[:200],
                    fabricated_entity=citation.strip(),
                    entity_type=FabricationType.CITATION,
                    severity=0.90,
                    detail=f"Citation '{citation.strip()}' not found in any source fact",
                ))

        # --- Check 5: Proper nouns ---
        for m in _PROPER_RE.finditer(claim):
            name = m.group(0)
            if not _entity_in_facts(name, fact_texts):
                results.append(FabricationResult(
                    claim_index=attr.claim_index,
                    claim_text=claim[:200],
                    fabricated_entity=name,
                    entity_type=FabricationType.PROPER_NOUN,
                    severity=0.65,
                    detail=f"Name '{name}' not found in any source fact",
                ))

    return results
