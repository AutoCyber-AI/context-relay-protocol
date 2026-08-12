# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Attribution Scorer — map claims to envelope facts (§7.14.3).

For each factual claim in the LLM output, scores how likely it came from
each envelope fact vs. parametric knowledge.  Uses two signals:

  1. **Semantic similarity**: When available, uses dense sentence-transformer
     embeddings (all-MiniLM-L6-v2, 384-dim) for genuine semantic comparison.
     Falls back to hash-projected bag-of-words when the model is unavailable.
  2. **Lexical overlap**: Token-level Jaccard overlap — fast, complements
     semantic similarity for surface-level attribution.

The composite score is a weighted blend:
    composite = semantic_weight × semantic + lexical_weight × lexical

Claims with no fact scoring above ``similarity_threshold`` are flagged
as PARAMETRIC (likely from model training data).  Claims with a top score
between ``mixed_threshold`` and ``similarity_threshold`` are MIXED.
"""

from __future__ import annotations

import hashlib
import logging
import math
import re
from collections.abc import Sequence
from typing import Any

from crp.envelope.packer import PackedFact

from ._embeddings import cosine_similarity as _dense_cosine
from ._embeddings import encode_texts
from ._types import (
    AttributionType,
    ClaimAttribution,
    ClaimType,
    FactScore,
    ProvenanceConfig,
)
from .claim_detector import DetectedClaim

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal: lightweight text vectorisation (mirrors crp.envelope.decomposer)
# ---------------------------------------------------------------------------

_STOP = frozenset(
    [
        "a", "an", "the", "and", "or", "but", "in", "on", "at", "to",
        "for", "of", "is", "it", "its", "are", "was", "were", "be",
        "been", "being", "have", "has", "had", "do", "does", "did",
        "will", "would", "shall", "should", "may", "might", "can",
        "could", "this", "that", "these", "those", "i", "we", "you",
        "he", "she", "they", "me", "us", "him", "her", "them", "my",
        "our", "your", "his", "their", "with", "from", "by", "as",
        "not", "no",
    ]
)

_EMBED_DIM = 256


def _tokenize(text: str) -> list[str]:
    """Lower-case word tokeniser (alphanum only, stopwords removed)."""
    return [w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in _STOP]


def _bag_vector(tokens: Sequence[str], dim: int = _EMBED_DIM) -> list[float]:
    """Sparse bag-of-words vector with hash projection, L2-normalised."""
    vec = [0.0] * dim
    for tok in tokens:
        idx = int(hashlib.sha256(tok.encode()).hexdigest(), 16) % dim
        vec[idx] += 1.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    """Cosine similarity between two equal-length vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a)) or 1e-12
    norm_b = math.sqrt(sum(x * x for x in b)) or 1e-12
    return dot / (norm_a * norm_b)


def _lexical_overlap(tokens_a: list[str], tokens_b: list[str]) -> float:
    """Token-level Jaccard overlap (|intersection| / |union|)."""
    if not tokens_a or not tokens_b:
        return 0.0
    set_a = set(tokens_a)
    set_b = set(tokens_b)
    intersection = set_a & set_b
    union = set_a | set_b
    return len(intersection) / len(union) if union else 0.0


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def score_claim_against_facts(
    claim: DetectedClaim,
    packed_facts: list[PackedFact],
    *,
    config: ProvenanceConfig | None = None,
    _embedder_override: Any = None,
) -> ClaimAttribution:
    """Score a single claim against all envelope facts.

    Attempts to use dense sentence-transformer embeddings for semantic
    similarity.  Falls back to hash-projected bag-of-words if the
    embedding model is unavailable.

    Args:
        claim: Detected claim from claim_detector.
        packed_facts: Facts that were packed into the envelope.
        config: Scoring configuration (thresholds, weights).
        _embedder_override: Injected embedding model for testing.

    Returns:
        ClaimAttribution with ranked fact scores and attribution type.
    """
    cfg = config or ProvenanceConfig()

    claim_tokens = _tokenize(claim.text)

    # --- Try dense embeddings first ---
    texts_to_encode = [claim.text] + [pf.text for pf in packed_facts]
    dense_embeddings = encode_texts(texts_to_encode, _model_override=_embedder_override)
    use_dense = dense_embeddings is not None and len(dense_embeddings) == len(texts_to_encode)

    if use_dense:
        claim_emb = dense_embeddings[0]
        fact_embs = dense_embeddings[1:]
    else:
        # Fallback: hash-projected bag-of-words
        claim_vec = _bag_vector(claim_tokens)

    fact_scores: list[FactScore] = []

    for i, pf in enumerate(packed_facts):
        fact_tokens = _tokenize(pf.text)

        if use_dense:
            semantic = max(_dense_cosine(claim_emb, fact_embs[i]), 0.0)
        else:
            fact_vec = _bag_vector(fact_tokens)
            semantic = max(_cosine(claim_vec, fact_vec), 0.0)

        lexical = _lexical_overlap(claim_tokens, fact_tokens)

        composite = (
            cfg.semantic_weight * semantic
            + cfg.lexical_weight * lexical
        )

        fact_scores.append(FactScore(
            fact_id=pf.fact_id,
            fact_text_preview=pf.text[:cfg.fact_preview_length],
            semantic_similarity=round(semantic, 4),
            lexical_overlap=round(lexical, 4),
            composite_score=round(composite, 4),
            fact_source_window="",   # Filled by provenance chain builder
            fact_extraction_stage=0,  # Filled by provenance chain builder
        ))

    # Sort by composite score descending
    fact_scores.sort(key=lambda fs: fs.composite_score, reverse=True)

    # Determine attribution type from top score AND its constituent signals.
    # A claim is only CONTEXT_GROUNDED if it clears both the composite
    # similarity threshold and per-signal minima. This stops unrelated facts
    # loaded into CKF from masking fabricated claims.
    top_score = fact_scores[0] if fact_scores else None
    top = top_score.composite_score if top_score else 0.0
    top_sem = top_score.semantic_similarity if top_score else 0.0
    top_lex = top_score.lexical_overlap if top_score else 0.0

    if (
        top >= cfg.similarity_threshold
        and top_sem >= cfg.min_grounding_semantic
        and top_lex >= cfg.min_grounding_lexical
    ):
        attr_type = AttributionType.CONTEXT_GROUNDED
    elif (
        top >= cfg.mixed_threshold
        and top_sem >= cfg.min_mixed_semantic
    ):
        attr_type = AttributionType.MIXED
    elif top > 0.0:
        attr_type = AttributionType.PARAMETRIC
    else:
        attr_type = AttributionType.UNCERTAIN

    # Confidence: distance from thresholds → 0.5–0.95 range
    if attr_type == AttributionType.CONTEXT_GROUNDED:
        confidence = min(0.60 + (top - cfg.similarity_threshold), 0.95)
    elif attr_type == AttributionType.MIXED:
        confidence = 0.40 + (top - cfg.mixed_threshold) * 0.5
    elif attr_type == AttributionType.PARAMETRIC:
        confidence = 0.50 + (cfg.mixed_threshold - top) * 0.3
    else:
        confidence = 0.20

    return ClaimAttribution(
        claim_text=claim.text,
        claim_index=claim.index,
        claim_type=claim.claim_type,
        attributed_facts=fact_scores[:5],  # Top-5 facts per claim
        top_score=round(top, 4),
        attribution_type=attr_type,
        confidence=round(min(max(confidence, 0.0), 1.0), 4),
    )


def score_all_claims(
    claims: list[DetectedClaim],
    packed_facts: list[PackedFact],
    *,
    config: ProvenanceConfig | None = None,
    _embedder_override: Any = None,
) -> list[ClaimAttribution]:
    """Score all claims against all envelope facts.

    Only FACTUAL_CLAIM and HEDGE types are scored against facts.
    Other types (OPINION, PROCEDURAL, CONNECTIVE) are returned with
    empty attribution (they don't require source grounding).

    Args:
        claims: All detected claims from claim_detector.
        packed_facts: Facts that were packed into the envelope.
        config: Scoring configuration.
        _embedder_override: Injected embedding model for testing.

    Returns:
        List of ClaimAttribution objects in claim order.
    """
    cfg = config or ProvenanceConfig()
    attributions: list[ClaimAttribution] = []

    for claim in claims:
        if claim.claim_type in (ClaimType.FACTUAL_CLAIM, ClaimType.HEDGE):
            attr = score_claim_against_facts(
                claim, packed_facts, config=cfg,
                _embedder_override=_embedder_override,
            )
        else:
            # Non-factual claims don't need source attribution
            attr = ClaimAttribution(
                claim_text=claim.text,
                claim_index=claim.index,
                claim_type=claim.claim_type,
                attributed_facts=[],
                top_score=0.0,
                attribution_type=AttributionType.UNCERTAIN,
                confidence=0.0,
            )
        attributions.append(attr)

    return attributions
