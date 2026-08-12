# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Contradiction Detector — catch self-contradictions in LLM output.

Within the same dispatch window:
   Claim 2: "The system is secure."
   Claim 7: "The system has critical vulnerabilities."

Across windows (if prior claims supplied):
   Window 1: "Revenue increased 10%."
   Window 3: "Revenue declined significantly."

This module detects contradictions through three signals:
  1. NEGATION conflicts — same content words + negation flip
  2. NUMBER conflicts — same entity referenced with different values
  3. SEMANTIC conflicts — high similarity + opposing sentiment signals
"""

from __future__ import annotations

import re

from ._types import (
    ClaimAttribution,
    ClaimType,
    ContradictionResult,
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_NEGATION_WORDS = frozenset({
    "not", "no", "never", "neither", "nor", "none",
    "doesn't", "don't", "didn't", "isn't", "aren't", "wasn't",
    "weren't", "won't", "wouldn't", "shouldn't", "couldn't",
    "can't", "cannot", "hasn't", "haven't", "hadn't",
})

_POSITIVE_SIGNALS = frozenset({
    "increased", "grew", "improved", "succeeded", "safe",
    "secure", "stable", "reliable", "positive", "effective",
    "beneficial", "strong", "healthy", "profitable", "rising",
    "gaining", "expanding", "accelerating",
})

_NEGATIVE_SIGNALS = frozenset({
    "decreased", "declined", "worsened", "failed", "unsafe",
    "insecure", "unstable", "unreliable", "negative", "ineffective",
    "harmful", "weak", "unhealthy", "unprofitable", "falling",
    "losing", "contracting", "decelerating", "vulnerable",
    "critical", "severe", "dangerous",
})

# Numbers in context: extract (subject_words, number_value) pairs
_NUM_RE = re.compile(r"(\d[\d,]*(?:\.\d+)?)\s*%?")


def _content_words(text: str) -> set[str]:
    """Extract non-stopword content words (lowered)."""
    stop = {
        "a", "an", "the", "and", "or", "but", "in", "on", "at", "to",
        "for", "of", "is", "it", "are", "was", "were", "be", "been",
        "being", "have", "has", "had", "this", "that", "these", "those",
        "with", "from", "by", "as", "will", "would",
    }
    return {
        w for w in re.findall(r"[a-z]+", text.lower())
        if w not in stop and len(w) > 2
    }


def _has_negation(text: str) -> bool:
    """Check if text contains negation words."""
    words = set(re.findall(r"[a-z']+", text.lower()))
    return bool(words & _NEGATION_WORDS)


def _sentiment_signals(text: str) -> tuple[set[str], set[str]]:
    """Extract positive and negative sentiment signal words."""
    words = set(re.findall(r"[a-z]+", text.lower()))
    return words & _POSITIVE_SIGNALS, words & _NEGATIVE_SIGNALS


def _extract_numbers(text: str) -> list[str]:
    """Extract numeric values."""
    return [m.group(1).replace(",", "") for m in _NUM_RE.finditer(text)]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def detect_contradictions(
    attributions: list[ClaimAttribution],
    *,
    prior_claims: list[str] | None = None,
    content_overlap_threshold: float = 0.30,
) -> list[ContradictionResult]:
    """Detect contradictions between claims.

    Checks all factual/hedge claim pairs within the current window for
    three types of contradiction:
      1. **NEGATION** — Same content + negation flip
      2. **NUMBER_CONFLICT** — Same topic + different numbers
      3. **SEMANTIC** — High word overlap + opposing sentiment

    If ``prior_claims`` are provided, also checks current claims against
    them for cross-window contradictions.

    Args:
        attributions: Scored claim attributions for the current window.
        prior_claims: Optional list of claim texts from prior windows.
        content_overlap_threshold: Minimum content word overlap ratio
                                   (Jaccard) to consider two claims as
                                   discussing the same topic.

    Returns:
        List of ContradictionResult — one per detected contradiction.
    """
    results: list[ContradictionResult] = []

    # Collect factual claims
    factual_attrs = [
        a for a in attributions
        if a.claim_type in (ClaimType.FACTUAL_CLAIM, ClaimType.HEDGE)
    ]

    # --- Intra-window contradictions ---
    for i in range(len(factual_attrs)):
        for j in range(i + 1, len(factual_attrs)):
            a = factual_attrs[i]
            b = factual_attrs[j]

            result = _check_pair(
                a.claim_index, a.claim_text,
                b.claim_index, b.claim_text,
                content_overlap_threshold,
            )
            if result:
                results.append(result)

    # --- Cross-window contradictions ---
    if prior_claims:
        for attr in factual_attrs:
            for pi, prior in enumerate(prior_claims):
                result = _check_pair(
                    attr.claim_index, attr.claim_text,
                    -(pi + 1), prior,  # negative index = prior window
                    content_overlap_threshold,
                )
                if result:
                    results.append(result)

    return results


def _check_pair(
    idx_a: int, text_a: str,
    idx_b: int, text_b: str,
    overlap_threshold: float,
) -> ContradictionResult | None:
    """Check a pair of claims for contradiction."""
    words_a = _content_words(text_a)
    words_b = _content_words(text_b)

    if not words_a or not words_b:
        return None

    # Content overlap (Jaccard)
    intersection = words_a & words_b
    union = words_a | words_b
    overlap = len(intersection) / len(union) if union else 0.0

    if overlap < overlap_threshold:
        return None  # Different topics — can't contradict

    # --- Check 1: Negation flip ---
    neg_a = _has_negation(text_a)
    neg_b = _has_negation(text_b)

    if neg_a != neg_b:
        return ContradictionResult(
            claim_a_index=idx_a,
            claim_a_text=text_a[:200],
            claim_b_index=idx_b,
            claim_b_text=text_b[:200],
            contradiction_type="NEGATION",
            severity=0.85,
            detail=(
                f"Claims share {len(intersection)} content words but "
                f"one contains negation and the other does not"
            ),
        )

    # --- Check 2: Number conflict ---
    nums_a = _extract_numbers(text_a)
    nums_b = _extract_numbers(text_b)

    if nums_a and nums_b:
        # If same topic but different numbers
        shared_nums = set(nums_a) & set(nums_b)
        diff_nums_a = set(nums_a) - set(nums_b)
        diff_nums_b = set(nums_b) - set(nums_a)

        if diff_nums_a and diff_nums_b and not shared_nums:
            return ContradictionResult(
                claim_a_index=idx_a,
                claim_a_text=text_a[:200],
                claim_b_index=idx_b,
                claim_b_text=text_b[:200],
                contradiction_type="NUMBER_CONFLICT",
                severity=0.75,
                detail=(
                    f"Claims about same topic use different numbers: "
                    f"{', '.join(sorted(diff_nums_a)[:3])} vs "
                    f"{', '.join(sorted(diff_nums_b)[:3])}"
                ),
            )

    # --- Check 3: Semantic opposition ---
    pos_a, neg_sig_a = _sentiment_signals(text_a)
    pos_b, neg_sig_b = _sentiment_signals(text_b)

    # One positive + other negative on same topic
    if (pos_a and neg_sig_b and not neg_sig_a) or (pos_b and neg_sig_a and not neg_sig_b):
        return ContradictionResult(
            claim_a_index=idx_a,
            claim_a_text=text_a[:200],
            claim_b_index=idx_b,
            claim_b_text=text_b[:200],
            contradiction_type="SEMANTIC",
            severity=0.70,
            detail=(
                f"Claims about same topic have opposing sentiment: "
                f"positive signals {sorted(pos_a | pos_b)[:3]}, "
                f"negative signals {sorted(neg_sig_a | neg_sig_b)[:3]}"
            ),
        )

    return None
