# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Distortion Detector — catch when grounded claims misrepresent source facts.

The most dangerous failure in AI attribution: a claim is scored as
CONTEXT_GROUNDED (high similarity to a source fact) but the model has
subtly CHANGED a key detail — a number, a negation, a qualifier.
The auditor sees "grounded, confidence 0.89" and trusts it.  But the
claim is wrong.

This module catches six distortion types:
  - NUMBER_CHANGED:       "10%" → "15%"
  - NEGATION_FLIP:        "is safe" → "is not safe"
  - QUALIFIER_DROPPED:    "approximately 10" → "10" (false precision)
  - QUALIFIER_ADDED:      "10" → "always 10" (over-generalisation)
  - SCOPE_CHANGED:        "in Q3" → "annually"
  - ENTITY_SUBSTITUTED:   "Company A" → "Company B"
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from crp.envelope.packer import PackedFact

from ._embeddings import cosine_similarity as _emb_cosine
from ._embeddings import encode_texts as _encode_texts
from ._types import (
    AttributionType,
    ClaimAttribution,
    DistortionResult,
    DistortionType,
)


# ---------------------------------------------------------------------------
# Internal: entity extractors
# ---------------------------------------------------------------------------

# Numbers: integers, decimals, with optional leading $ or trailing %
_NUM_RE = re.compile(
    r"(?<![a-zA-Z])"           # not preceded by letter
    r"\$?\s*"                  # optional $
    r"(\d[\d,]*(?:\.\d+)?)"   # the number itself
    r"\s*%?"                   # optional %
)

# Negation words
_NEGATION_WORDS = frozenset({
    "not", "no", "never", "neither", "nor", "none", "nobody",
    "nothing", "nowhere", "hardly", "scarcely", "barely",
    "doesn't", "don't", "didn't", "isn't", "aren't", "wasn't",
    "weren't", "won't", "wouldn't", "shouldn't", "couldn't",
    "can't", "cannot", "hasn't", "haven't", "hadn't",
})

# Qualifier words that add hedging / precision / universality
_HEDGE_QUALIFIERS = frozenset({
    "approximately", "roughly", "about", "around", "nearly",
    "possibly", "possibly", "perhaps", "maybe", "likely",
    "probably", "potentially", "estimated", "up to",
    "might", "could", "may", "suggest", "suggests",
})
_CERTAINTY_QUALIFIERS = frozenset({
    "exactly", "precisely", "always", "never", "definitely",
    "certainly", "absolutely", "guaranteed", "invariably",
    "exclusively", "solely", "only",
})

# Scope modifiers
_SCOPE_PATTERNS = re.compile(
    r"\b("
    r"in\s+Q[1-4]|per\s+quarter|quarterly"
    r"|annually|per\s+year|yearly|year-over-year|yoy"
    r"|monthly|per\s+month|week(?:ly)?|daily"
    r"|globally|worldwide|nationally|regionally|locally"
    r"|all\s+(?:users?|customers?|clients?|regions?)"
    r"|some\s+(?:users?|customers?|clients?|regions?)"
    r")\b",
    re.IGNORECASE,
)

# Proper nouns: capitalized words (excluding common sentence starters)
_PROPER_NOUN_RE = re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b")


def _extract_numbers(text: str) -> list[str]:
    """Extract all numeric values from text as normalised strings."""
    raw = _NUM_RE.findall(text)
    return [n.replace(",", "") for n in raw]


def _extract_negations(text: str) -> set[str]:
    """Extract negation words present in text."""
    words = set(re.findall(r"[a-z']+", text.lower()))
    return words & _NEGATION_WORDS


def _extract_qualifiers(text: str) -> tuple[set[str], set[str]]:
    """Return (hedge_qualifiers_found, certainty_qualifiers_found)."""
    words_lower = text.lower()
    hedges = {q for q in _HEDGE_QUALIFIERS if q in words_lower}
    certs = {q for q in _CERTAINTY_QUALIFIERS if q in words_lower}
    return hedges, certs


def _extract_scopes(text: str) -> list[str]:
    """Extract scope modifiers from text."""
    return [m.group(1).lower() for m in _SCOPE_PATTERNS.finditer(text)]


def _extract_proper_nouns(text: str) -> set[str]:
    """Extract multi-word proper nouns."""
    return {m.group(0) for m in _PROPER_NOUN_RE.finditer(text)}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def detect_distortions(
    attributions: list[ClaimAttribution],
    packed_facts: list[PackedFact],
) -> list[DistortionResult]:
    """Detect distortions in context-grounded claims.

    For each CONTEXT_GROUNDED or MIXED attribution, compares the claim
    against its top source fact looking for subtle but critical changes:
    numbers altered, negations flipped, qualifiers dropped, etc.

    Args:
        attributions: Scored claim attributions from attribution_scorer.
        packed_facts: All envelope facts (for full-text lookup).

    Returns:
        List of DistortionResult — one per detected distortion.
        Empty list means no distortions found (perfect fidelity).
    """
    # Build fact lookup by ID for O(1) access
    fact_lookup: dict[str, str] = {pf.fact_id: pf.text for pf in packed_facts}

    results: list[DistortionResult] = []

    for attr in attributions:
        # Only check grounded/mixed claims — these are the "trusted" ones
        if attr.attribution_type not in (
            AttributionType.CONTEXT_GROUNDED,
            AttributionType.MIXED,
        ):
            continue

        if not attr.attributed_facts:
            continue

        # Weakly-attributed claims are exactly where distortions are dangerous,
        # because a fabricated claim can score just high enough to be marked
        # MIXED. Run the check for all grounded/mixed claims and scale severity
        # by attribution strength instead of skipping.
        attribution_strength = attr.attributed_facts[0].composite_score

        # Compare against top-scoring source fact
        top_fact = attr.attributed_facts[0]
        fact_text = fact_lookup.get(top_fact.fact_id, top_fact.fact_text_preview)

        # --- Check 1: Number changes ---
        claim_nums = _extract_numbers(attr.claim_text)
        fact_nums = _extract_numbers(fact_text)

        if claim_nums and fact_nums:
            # Numbers present in claim but NOT in fact → possible distortion
            fact_num_set = set(fact_nums)
            for cn in claim_nums:
                if cn not in fact_num_set and fact_nums:
                    # Is there a "close" number in the fact? (same magnitude)
                    for fn in fact_nums:
                        try:
                            cv, fv = float(cn), float(fn)
                            # Same order of magnitude but different value
                            if fv != 0 and 0.1 < abs(cv / fv) < 10.0 and cv != fv:
                                severity = min(abs(cv - fv) / max(abs(fv), 1e-9), 1.0)
                                results.append(DistortionResult(
                                    claim_index=attr.claim_index,
                                    claim_text=attr.claim_text[:200],
                                    source_fact_id=top_fact.fact_id,
                                    source_fact_preview=fact_text[:120],
                                    distortion_type=DistortionType.NUMBER_CHANGED,
                                    severity=round(min(severity, 1.0), 2),
                                    detail=(
                                        f"Claim uses '{cn}' but source fact "
                                        f"uses '{fn}'"
                                    ),
                                    claim_value=cn,
                                    fact_value=fn,
                                ))
                                break
                        except ValueError:
                            continue

        # --- Check 2: Negation flip ---
        claim_negs = _extract_negations(attr.claim_text)
        fact_negs = _extract_negations(fact_text)

        # One has negation, the other doesn't → potential flip
        if claim_negs and not fact_negs:
            results.append(DistortionResult(
                claim_index=attr.claim_index,
                claim_text=attr.claim_text[:200],
                source_fact_id=top_fact.fact_id,
                source_fact_preview=fact_text[:120],
                distortion_type=DistortionType.NEGATION_FLIP,
                severity=0.90,
                detail=(
                    f"Claim contains negation ({', '.join(sorted(claim_negs)[:3])}) "
                    f"but source fact does not"
                ),
                claim_value=", ".join(sorted(claim_negs)[:3]),
                fact_value="(no negation)",
            ))
        elif fact_negs and not claim_negs:
            results.append(DistortionResult(
                claim_index=attr.claim_index,
                claim_text=attr.claim_text[:200],
                source_fact_id=top_fact.fact_id,
                source_fact_preview=fact_text[:120],
                distortion_type=DistortionType.NEGATION_FLIP,
                severity=0.90,
                detail=(
                    f"Source fact contains negation ({', '.join(sorted(fact_negs)[:3])}) "
                    f"but claim does not"
                ),
                claim_value="(no negation)",
                fact_value=", ".join(sorted(fact_negs)[:3]),
            ))

        # --- Check 3: Qualifier changes ---
        claim_hedges, claim_certs = _extract_qualifiers(attr.claim_text)
        fact_hedges, fact_certs = _extract_qualifiers(fact_text)

        # Fact has hedge qualifier but claim dropped it → false precision
        dropped = fact_hedges - claim_hedges
        if dropped and not claim_hedges:
            results.append(DistortionResult(
                claim_index=attr.claim_index,
                claim_text=attr.claim_text[:200],
                source_fact_id=top_fact.fact_id,
                source_fact_preview=fact_text[:120],
                distortion_type=DistortionType.QUALIFIER_DROPPED,
                severity=0.60,
                detail=(
                    f"Source fact qualifies with '{', '.join(sorted(dropped)[:3])}' "
                    f"but claim states without qualification"
                ),
                claim_value="(unqualified)",
                fact_value=", ".join(sorted(dropped)[:3]),
            ))

        # Claim adds certainty qualifier not in fact → over-generalisation
        added_certs = claim_certs - fact_certs
        if added_certs:
            results.append(DistortionResult(
                claim_index=attr.claim_index,
                claim_text=attr.claim_text[:200],
                source_fact_id=top_fact.fact_id,
                source_fact_preview=fact_text[:120],
                distortion_type=DistortionType.QUALIFIER_ADDED,
                severity=0.55,
                detail=(
                    f"Claim adds certainty qualifier '{', '.join(sorted(added_certs)[:3])}' "
                    f"not present in source fact"
                ),
                claim_value=", ".join(sorted(added_certs)[:3]),
                fact_value="(no such qualifier)",
            ))

        # --- Check 4: Scope change ---
        claim_scopes = _extract_scopes(attr.claim_text)
        fact_scopes = _extract_scopes(fact_text)

        if claim_scopes and fact_scopes:
            claim_scope_set = set(claim_scopes)
            fact_scope_set = set(fact_scopes)
            if claim_scope_set != fact_scope_set:
                results.append(DistortionResult(
                    claim_index=attr.claim_index,
                    claim_text=attr.claim_text[:200],
                    source_fact_id=top_fact.fact_id,
                    source_fact_preview=fact_text[:120],
                    distortion_type=DistortionType.SCOPE_CHANGED,
                    severity=0.70,
                    detail=(
                        f"Claim scope '{', '.join(sorted(claim_scope_set))}' "
                        f"differs from fact scope '{', '.join(sorted(fact_scope_set))}'"
                    ),
                    claim_value=", ".join(sorted(claim_scope_set)),
                    fact_value=", ".join(sorted(fact_scope_set)),
                ))

        # --- Check 5: Entity substitution ---
        claim_entities = _extract_proper_nouns(attr.claim_text)
        fact_entities = _extract_proper_nouns(fact_text)

        if claim_entities and fact_entities:
            new_entities = claim_entities - fact_entities
            missing_entities = fact_entities - claim_entities
            # If entities were swapped (some added, some removed)
            if new_entities and missing_entities:
                results.append(DistortionResult(
                    claim_index=attr.claim_index,
                    claim_text=attr.claim_text[:200],
                    source_fact_id=top_fact.fact_id,
                    source_fact_preview=fact_text[:120],
                    distortion_type=DistortionType.ENTITY_SUBSTITUTED,
                    severity=0.80,
                    detail=(
                        f"Claim introduces entities "
                        f"'{', '.join(sorted(new_entities)[:3])}' while fact has "
                        f"'{', '.join(sorted(missing_entities)[:3])}'"
                    ),
                    claim_value=", ".join(sorted(new_entities)[:3]),
                    fact_value=", ".join(sorted(missing_entities)[:3]),
                ))

    # --- Check 6: Semantic drift (P-3) ---
    # Use sentence-transformer embeddings to detect meaning-level
    # distortions that regex patterns cannot catch (specificity loss,
    # causation inflation, scope generalisation).
    _semantic_drift_check(attributions, fact_lookup, results)

    # Scale distortion severity by attribution strength. A fabricated claim
    # that barely reaches MIXED should not produce a high-severity distortion
    # on an unrelated fact; a strongly-grounded claim that misrepresents its
    # source fact should remain severe. We dampen weak matches rather than
    # zero them out.
    strength_by_claim: dict[int, float] = {
        attr.claim_index: attr.attributed_facts[0].composite_score
        for attr in attributions
        if attr.attributed_facts
    }
    for r in results:
        strength = strength_by_claim.get(r.claim_index, 1.0)
        scale = min(1.0, strength + 0.15)
        r.severity = round(min(r.severity * scale, 1.0), 2)

    return results


def _semantic_drift_check(
    attributions: list[ClaimAttribution],
    fact_lookup: dict[str, str],
    results: list[DistortionResult],
    *,
    _embedder_override: object = None,
    drift_threshold: float = 0.65,
) -> None:
    """Detect semantic drift using dense embeddings.

    Claims that are CONTEXT_GROUNDED but have low semantic similarity
    to their source fact (below drift_threshold) may be paraphrasing
    in a way that changes meaning — something regex can't catch.

    Only triggers when embeddings are available; degrades silently.
    """
    # Collect grounded claim-fact pairs
    pairs: list[tuple[ClaimAttribution, str, str]] = []
    for attr in attributions:
        if attr.attribution_type not in (
            AttributionType.CONTEXT_GROUNDED,
            AttributionType.MIXED,
        ):
            continue
        if not attr.attributed_facts:
            continue
        top_fact = attr.attributed_facts[0]
        fact_text = fact_lookup.get(top_fact.fact_id, top_fact.fact_text_preview)
        pairs.append((attr, top_fact.fact_id, fact_text))

    if not pairs:
        return

    # Batch-encode all claims and facts together
    all_texts = []
    for attr, _, fact_text in pairs:
        all_texts.append(attr.claim_text)
        all_texts.append(fact_text)

    embs = _encode_texts(all_texts, _model_override=_embedder_override)
    if embs is None:
        return  # Embeddings unavailable — silent degradation

    for i, (attr, fact_id, fact_text) in enumerate(pairs):
        claim_emb = embs[i * 2]
        fact_emb = embs[i * 2 + 1]
        sim = max(0.0, _emb_cosine(claim_emb, fact_emb))

        if sim < drift_threshold:
            # Already caught by regex checks? Skip if same claim_index
            # already has a distortion result to avoid double-flagging
            already_flagged = any(
                r.claim_index == attr.claim_index for r in results
            )
            if not already_flagged:
                results.append(DistortionResult(
                    claim_index=attr.claim_index,
                    claim_text=attr.claim_text[:200],
                    source_fact_id=fact_id,
                    source_fact_preview=fact_text[:120],
                    distortion_type=DistortionType.SEMANTIC_DRIFT,
                    severity=round(1.0 - sim, 2),
                    detail=(
                        f"Semantic similarity {sim:.2f} below threshold "
                        f"{drift_threshold:.2f} — possible meaning-level "
                        f"distortion not caught by lexical checks"
                    ),
                    claim_value=f"similarity={sim:.2f}",
                    fact_value=f"threshold={drift_threshold:.2f}",
                ))
