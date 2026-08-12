# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Semantic Entailment Verifier — ML-powered claim↔fact verification (§7.14.3).

**THE PROBLEM rule-based fidelity cannot solve:**

    Fact:  "The treatment significantly reduced patient mortality."
    Claim: "The treatment showed some positive outcomes for patients."

Lexically similar.  Zero number distortions.  No negation flip.
But the claim *lost critical specificity* — a regulator reading the
claim would make a DIFFERENT decision than one reading the fact.

Rule-based detectors catch surface edits: 10→25, "safe"→"not safe".
They *cannot* detect:
  - Specificity loss ("reduced mortality" → "positive outcomes")
  - Causation inflation ("correlation observed" → "X causes Y")
  - Scope generalisation ("in clinical settings" → "broadly")
  - Hedging removal ("might reduce" → "reduces")

**THE SOLUTION: Natural Language Inference (NLI).**

A lightweight cross-encoder NLI model (~80 MB, CPU-only, <50 ms/pair)
classifies each (premise=fact, hypothesis=claim) pair as:
  - ENTAILED — claim logically follows from the fact ✅
  - NEUTRAL — claim is unrelated to the fact ⚠️
  - CONTRADICTION — claim conflicts with the fact ❌

This gives CRP a **semantic fidelity layer** that sits above the lexical
layer, catching meaning-level distortions no regex can reach.

When the NLI model is unavailable (not installed, resource-constrained),
the verifier degrades gracefully to a heuristic based on bag-of-words
similarity — still better than nothing, while flagging that the result
is heuristic-only.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Sequence
from typing import Any

from crp.envelope.packer import PackedFact

from ._embeddings import cosine_similarity as _emb_cosine
from ._embeddings import encode_texts as _encode_texts
from ._types import (
    AttributionType,
    ClaimAttribution,
    ClaimType,
    EntailmentLabel,
    EntailmentResult,
    ProvenanceConfig,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level model cache (lazy singleton)
# ---------------------------------------------------------------------------

_nli_model: Any = None
_nli_model_name: str = ""
_nli_load_failed: bool = False


def _get_nli_model(model_name: str) -> Any:
    """Lazy-load the NLI cross-encoder model (singleton).

    Returns the model or None if loading fails.
    """
    global _nli_model, _nli_model_name, _nli_load_failed  # noqa: PLW0603

    if _nli_load_failed:
        return None

    if _nli_model is not None and _nli_model_name == model_name:
        return _nli_model

    try:
        from sentence_transformers import CrossEncoder  # type: ignore[import-untyped]
        logger.info("Loading NLI model: %s", model_name)
        _nli_model = CrossEncoder(model_name)
        _nli_model_name = model_name
        return _nli_model
    except Exception as exc:
        logger.warning("NLI model unavailable (%s), using heuristic: %s", model_name, exc)
        _nli_load_failed = True
        return None


def reset_model_cache() -> None:
    """Reset the module-level model cache (for testing)."""
    global _nli_model, _nli_model_name, _nli_load_failed  # noqa: PLW0603
    _nli_model = None
    _nli_model_name = ""
    _nli_load_failed = False


# ---------------------------------------------------------------------------
# Heuristic fallback (when NLI model unavailable)
# ---------------------------------------------------------------------------

_STOP = frozenset({
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to",
    "for", "of", "is", "it", "are", "was", "were", "be", "been",
    "being", "have", "has", "had", "this", "that", "these", "those",
    "with", "from", "by", "as", "will", "would", "can", "could",
})

_NEGATION_WORDS = frozenset({
    "not", "no", "never", "neither", "nor", "none",
    "doesn't", "don't", "didn't", "isn't", "aren't", "wasn't",
    "weren't", "won't", "wouldn't", "shouldn't", "couldn't",
    "can't", "cannot", "hasn't", "haven't", "hadn't",
})


def _content_words(text: str) -> set[str]:
    return {
        w for w in re.findall(r"[a-z]+", text.lower())
        if w not in _STOP and len(w) > 2
    }


def _has_negation(text: str) -> bool:
    words = set(re.findall(r"[a-z']+", text.lower()))
    return bool(words & _NEGATION_WORDS)


def _heuristic_entailment(
    claim: str,
    fact: str,
) -> tuple[float, float, float]:
    """ML-driven heuristic entailment when the NLI cross-encoder is unavailable.

    Strategy (ordered by quality):
      1. Try dense sentence-transformer embeddings (cosine similarity)
         for genuine semantic comparison.  Maps cosine→NLI-like scores.
      2. Fall back to word overlap + negation if embeddings unavailable.

    Returns (entailment_score, contradiction_score, neutral_score).
    """
    # Short-circuit on empty input
    if not claim.strip() or not fact.strip():
        return 0.0, 0.0, 1.0

    # --- Attempt 1: Dense embedding similarity ---
    embs = _encode_texts([claim, fact])
    if embs is not None and len(embs) == 2:
        sim = max(0.0, min(1.0, _emb_cosine(embs[0], embs[1])))

        # Check negation asymmetry even with embeddings
        claim_neg = _has_negation(claim)
        fact_neg = _has_negation(fact)
        negation_flip = claim_neg != fact_neg

        if negation_flip and sim > 0.40:
            return 0.05, 0.75, 0.20

        # Map cosine similarity to NLI-like probability distribution
        if sim > 0.75:
            return 0.80, 0.03, 0.17
        elif sim > 0.55:
            return 0.55, 0.08, 0.37
        elif sim > 0.35:
            return 0.25, 0.10, 0.65
        else:
            return 0.08, 0.07, 0.85

    # --- Attempt 2: Bag-of-words fallback ---
    claim_words = _content_words(claim)
    fact_words = _content_words(fact)

    if not claim_words or not fact_words:
        return 0.0, 0.0, 1.0

    intersection = claim_words & fact_words
    union = claim_words | fact_words
    jaccard = len(intersection) / len(union) if union else 0.0

    # Check negation asymmetry
    claim_neg = _has_negation(claim)
    fact_neg = _has_negation(fact)
    negation_flip = claim_neg != fact_neg

    if negation_flip and jaccard > 0.25:
        # Same topic + negation flip = contradiction signal
        return 0.05, 0.80, 0.15
    elif jaccard > 0.50:
        return 0.70, 0.05, 0.25
    elif jaccard > 0.30:
        return 0.40, 0.10, 0.50
    else:
        return 0.10, 0.05, 0.85


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def verify_entailment(
    attributions: list[ClaimAttribution],
    packed_facts: Sequence[PackedFact],
    *,
    config: ProvenanceConfig | None = None,
    _model_override: Any = None,
) -> list[EntailmentResult]:
    """Verify semantic entailment between grounded claims and their source facts.

    For each CONTEXT_GROUNDED or MIXED claim, runs NLI inference against
    the top source fact.  Returns an EntailmentResult per checked pair.

    The NLI model classifies (premise=fact, hypothesis=claim):
      - ENTAILED: claim logically follows from fact
      - CONTRADICTION: claim conflicts with fact
      - NEUTRAL: claim is unrelated to fact

    When the NLI model is unavailable, falls back to a heuristic based on
    word overlap + negation detection.  The ``used_model`` field in each
    result indicates which method was used.

    Args:
        attributions: Scored claim attributions from the DPE pipeline.
        packed_facts: All envelope facts (for full-text lookup).
        config: ProvenanceConfig (controls model name, thresholds).
        _model_override: Override NLI model for testing (internal).

    Returns:
        List of EntailmentResult — one per checked claim-fact pair.
    """
    cfg = config or ProvenanceConfig()
    if not cfg.entailment_enabled:
        return []

    # Build fact lookup
    fact_lookup: dict[str, str] = {pf.fact_id: pf.text for pf in packed_facts}

    # Get or load NLI model
    model = _model_override or _get_nli_model(cfg.entailment_model)
    use_model = model is not None

    results: list[EntailmentResult] = []

    # Collect claim-fact pairs to verify
    pairs_to_check: list[tuple[ClaimAttribution, str, str]] = []
    for attr in attributions:
        if attr.attribution_type not in (
            AttributionType.CONTEXT_GROUNDED,
            AttributionType.MIXED,
        ):
            continue
        if attr.claim_type not in (ClaimType.FACTUAL_CLAIM, ClaimType.HEDGE):
            continue
        if not attr.attributed_facts:
            continue

        top_fact = attr.attributed_facts[0]
        fact_text = fact_lookup.get(top_fact.fact_id, top_fact.fact_text_preview)
        if not fact_text.strip():
            continue

        pairs_to_check.append((attr, top_fact.fact_id, fact_text))

    if not pairs_to_check:
        return []

    if use_model:
        # Batch NLI inference for efficiency
        nli_inputs = [
            (fact_text, attr.claim_text)  # premise=fact, hypothesis=claim
            for attr, _, fact_text in pairs_to_check
        ]
        try:
            raw_scores = model.predict(nli_inputs)
            # CrossEncoder NLI returns [contradiction, entailment, neutral]
            # or [entailment, neutral, contradiction] depending on model
            # Normalise via softmax-like interpretation
            for i, (attr, fact_id, fact_text) in enumerate(pairs_to_check):
                scores = raw_scores[i]
                # Standard NLI cross-encoder label order: [contradiction, entailment, neutral]
                if len(scores) == 3:
                    contradiction_s = float(scores[0])
                    entailment_s = float(scores[1])
                    neutral_s = float(scores[2])
                else:
                    # Fallback: treat as binary
                    entailment_s = float(scores[0]) if len(scores) > 0 else 0.0
                    contradiction_s = 0.0
                    neutral_s = 1.0 - entailment_s

                # Softmax normalisation
                import math
                vals = [entailment_s, contradiction_s, neutral_s]
                max_v = max(vals)
                exp_vals = [math.exp(v - max_v) for v in vals]
                total = sum(exp_vals)
                ent_p = exp_vals[0] / total
                con_p = exp_vals[1] / total
                neu_p = exp_vals[2] / total

                # Classify
                label, confidence = _classify_from_probs(ent_p, con_p, neu_p)

                results.append(EntailmentResult(
                    claim_index=attr.claim_index,
                    claim_text=attr.claim_text[:200],
                    fact_id=fact_id,
                    fact_text_preview=fact_text[:120],
                    label=label,
                    confidence=round(confidence, 4),
                    entailment_score=round(ent_p, 4),
                    contradiction_score=round(con_p, 4),
                    neutral_score=round(neu_p, 4),
                    used_model=True,
                ))
        except Exception as exc:
            logger.warning("NLI inference failed, falling back to heuristic: %s", exc)
            use_model = False

    if not use_model:
        # Heuristic fallback
        for attr, fact_id, fact_text in pairs_to_check:
            ent_s, con_s, neu_s = _heuristic_entailment(attr.claim_text, fact_text)
            label, confidence = _classify_from_probs(ent_s, con_s, neu_s)

            results.append(EntailmentResult(
                claim_index=attr.claim_index,
                claim_text=attr.claim_text[:200],
                fact_id=fact_id,
                fact_text_preview=fact_text[:120],
                label=label,
                confidence=round(confidence, 4),
                entailment_score=round(ent_s, 4),
                contradiction_score=round(con_s, 4),
                neutral_score=round(neu_s, 4),
                used_model=False,
            ))

    return results


def _classify_from_probs(
    ent_p: float,
    con_p: float,
    neu_p: float,
) -> tuple[EntailmentLabel, float]:
    """Classify into ENTAILED/CONTRADICTION/NEUTRAL from probabilities."""
    best = max(ent_p, con_p, neu_p)
    if con_p == best:
        return EntailmentLabel.CONTRADICTION, con_p
    elif ent_p == best:
        return EntailmentLabel.ENTAILED, ent_p
    else:
        return EntailmentLabel.NEUTRAL, neu_p
