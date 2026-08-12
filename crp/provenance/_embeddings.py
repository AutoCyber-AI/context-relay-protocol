# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Shared semantic embedding module for DPE components (§7.14.3).

Provides lazy-loaded sentence-transformer embeddings used by:
  - attribution_scorer (G-1): real semantic similarity vs hash-BOW
  - entailment_verifier (P-1): ML-driven fallback when NLI unavailable
  - distortion_detector (P-3): semantic drift detection

The model (all-MiniLM-L6-v2, ~80 MB, 384-dim, CPU-only) is loaded
once and shared across all components to avoid duplicate memory usage.
"""

from __future__ import annotations

import logging
import math
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level model cache (lazy singleton)
# ---------------------------------------------------------------------------

_model: Any = None
_model_load_failed: bool = False
_DEFAULT_MODEL = "all-MiniLM-L6-v2"


def get_embedder(*, model_name: str = _DEFAULT_MODEL) -> Any:
    """Lazy-load the SentenceTransformer model (singleton).

    Returns the model object or None if loading fails.
    """
    global _model, _model_load_failed  # noqa: PLW0603

    if _model_load_failed:
        return None

    if _model is not None:
        return _model

    try:
        from sentence_transformers import SentenceTransformer  # type: ignore[import-untyped]
        logger.info("Loading embedding model: %s", model_name)
        _model = SentenceTransformer(model_name)
        return _model
    except Exception as exc:
        logger.warning(
            "Embedding model unavailable (%s), semantic features degraded: %s",
            model_name, exc,
        )
        _model_load_failed = True
        return None


def encode_texts(
    texts: list[str],
    *,
    _model_override: Any = None,
) -> list[list[float]] | None:
    """Encode texts into dense embeddings.

    Args:
        texts: List of strings to encode.
        _model_override: Injected model for testing (skips singleton).

    Returns:
        List of embedding vectors (as lists of floats), or None if
        the model is unavailable.
    """
    model = _model_override or get_embedder()
    if model is None:
        return None

    try:
        embeddings = model.encode(texts, convert_to_numpy=True)
        return [emb.tolist() for emb in embeddings]
    except Exception as exc:
        logger.warning("Embedding encode failed: %s", exc)
        return None


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a)) or 1e-12
    norm_b = math.sqrt(sum(x * x for x in b)) or 1e-12
    return dot / (norm_a * norm_b)


def reset_cache() -> None:
    """Reset the module-level model cache (for testing)."""
    global _model, _model_load_failed  # noqa: PLW0603
    _model = None
    _model_load_failed = False
