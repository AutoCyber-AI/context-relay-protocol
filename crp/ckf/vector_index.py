# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""CKF vector index — FAISS-first ANN backend with graceful fallback (§3.8).

Default vector backend for CKF semantic similarity (CRPv6 Phase A).  Backend
selection order — the index never fails to construct:

1. **faiss** (``faiss-cpu``) — ``IndexFlatIP`` over L2-normalised vectors, so
   inner product == cosine similarity.
2. **hnswlib** — cosine-space HNSW (the pre-Phase-A default).
3. **numpy** — brute-force dot products over L2-normalised rows.
4. **pure Python** — keeps the zero-dependency core import-safe.

Embeddings come from sentence-transformers ``all-MiniLM-L6-v2`` (lazy
singleton, override with ``CRP_EMBEDDING_MODEL``; the canonical id lives in
``crp/ml/manifest.json`` under ``crp.embeddings.default``).  The model id in
use is recorded via :func:`active_embedding_model_id` per Invariant 5 —
Coverage Set, Turn Log and CKF facts must share one embedding model.
"""

from __future__ import annotations

import logging
import math
import os
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_MODEL_FALLBACK = "sentence-transformers/all-MiniLM-L6-v2"

# ---------------------------------------------------------------------------
# Embedding model resolution + lazy singleton encoder
# ---------------------------------------------------------------------------

_encoder: Any = None
_encoder_failed: bool = False
_encoder_model_id: str | None = None


def resolve_embedding_model_id() -> str:
    """Return the embedding model id: env override → manifest → fallback."""
    override = os.environ.get("CRP_EMBEDDING_MODEL", "").strip()
    if override:
        return override
    try:
        from crp.ml.downloader import load_manifest

        entry = load_manifest().get("models", {}).get("crp.embeddings.default", {})
        repo_id = str(entry.get("repo_id", "")).strip()
        if repo_id:
            return repo_id
    except Exception:  # noqa: BLE001
        pass
    return _DEFAULT_MODEL_FALLBACK


def get_encoder(model_id: str | None = None) -> Any:
    """Lazy-load the SentenceTransformer encoder (singleton).

    Returns the model object, or None if sentence-transformers is
    unavailable or the model cannot be loaded.  Never raises.
    """
    global _encoder, _encoder_failed, _encoder_model_id  # noqa: PLW0603

    resolved = model_id or resolve_embedding_model_id()
    if _encoder is not None and _encoder_model_id == resolved:
        return _encoder
    if _encoder_failed and model_id is None:
        return None

    try:
        from sentence_transformers import SentenceTransformer  # type: ignore[import-untyped]

        logger.info("Loading embedding model: %s", resolved)
        encoder = SentenceTransformer(resolved)
    except Exception as exc:
        logger.warning("Embedding model unavailable (%s): %s", resolved, exc)
        if model_id is None:
            _encoder_failed = True
        return None

    _encoder = encoder
    _encoder_model_id = resolved
    _encoder_failed = False
    return _encoder


def active_embedding_model_id() -> str | None:
    """Return the id of the loaded embedding model (Invariant 5), else None."""
    return _encoder_model_id


def encode_texts(
    texts: list[str],
    *,
    _encoder_override: Any = None,
) -> list[list[float]] | None:
    """Encode texts into dense embeddings (raw, unnormalised).

    Args:
        texts: Strings to encode.
        _encoder_override: Injected encoder for testing (skips singleton).

    Returns:
        One vector per input text, or None if no encoder is available.
    """
    model = _encoder_override or get_encoder()
    if model is None:
        return None
    try:
        embeddings = model.encode(list(texts), convert_to_numpy=True)
        return [
            [float(x) for x in (emb.tolist() if hasattr(emb, "tolist") else emb)]
            for emb in embeddings
        ]
    except Exception as exc:
        logger.warning("Embedding encode failed: %s", exc)
        return None


def reset_encoder() -> None:
    """Reset the module-level encoder cache (for testing)."""
    global _encoder, _encoder_failed, _encoder_model_id  # noqa: PLW0603
    _encoder = None
    _encoder_failed = False
    _encoder_model_id = None


# ---------------------------------------------------------------------------
# Backend probes (lazy imports — zero-dependency core stays import-safe)
# ---------------------------------------------------------------------------

def _try_faiss() -> tuple[Any, Any] | None:
    """Return (faiss, numpy) modules if both import, else None."""
    try:
        import faiss  # type: ignore[import-untyped]
        import numpy as np  # type: ignore[import-untyped]

        return faiss, np
    except ImportError:
        return None


def _try_hnswlib() -> Any:
    """Return the hnswlib module if importable, else None."""
    try:
        import hnswlib  # type: ignore[import-untyped]

        return hnswlib
    except ImportError:
        return None


def _try_numpy() -> Any:
    """Return the numpy module if importable, else None."""
    try:
        import numpy as np  # type: ignore[import-untyped]

        return np
    except ImportError:
        return None


def _l2_normalise(vec: list[float]) -> list[float]:
    """Return the L2-normalised copy of *vec* (faiss IP == cosine)."""
    norm = math.sqrt(sum(x * x for x in vec))
    if norm < 1e-12:
        return [float(x) for x in vec]
    return [float(x) / norm for x in vec]


# ---------------------------------------------------------------------------
# VectorIndex
# ---------------------------------------------------------------------------

class VectorIndex:
    """Cosine-similarity vector index: faiss → hnswlib → numpy → pure Python.

    Duck-type compatible with the legacy ``HNSWIndex`` wrapper (``add``,
    ``query``, ``count``) so it can route through the existing CKF semantic
    fallback path.  All vectors are L2-normalised on the way in, so scores
    returned by :meth:`query` are cosine similarities in [-1, 1].

    Attributes:
        embedding_model_id: Embedding model id this index is paired with
            (Invariant 5 — recorded, never silently mixed).
    """

    def __init__(
        self,
        dim: int,
        max_elements: int = 10_000,
        encoder: Callable[[list[str]], list[list[float]]] | None = None,
    ) -> None:
        """Create an index for *dim*-dimensional embeddings.

        Args:
            dim: Embedding dimension.
            max_elements: Initial capacity (hnswlib backend; auto-resizes).
            encoder: Optional text encoder ``list[str] -> list[list[float]]``
                for :meth:`add_texts` / :meth:`query_text`.  Defaults to the
                sentence-transformers singleton.
        """
        self._dim = dim
        self._max_elements = max_elements
        self._encoder = encoder
        self.embedding_model_id = resolve_embedding_model_id()

        self._ids: list[str] = []
        # Normalised rows — the source of truth every backend can fall back to.
        self._vectors: list[list[float]] = []
        self._backend = "python"
        self._faiss: Any = None
        self._np: Any = None
        self._hnsw: Any = None

        self._init_backend()

    # -- Backend init ---------------------------------------------------------

    def _init_backend(self) -> None:
        """Probe faiss → hnswlib → numpy → pure Python. Never raises."""
        faiss_bundle = _try_faiss()
        if faiss_bundle is not None:
            faiss, np = faiss_bundle
            try:
                self._faiss = faiss.IndexFlatIP(self._dim)
                self._np = np
                self._backend = "faiss"
                return
            except Exception:  # noqa: BLE001
                logger.warning("faiss IndexFlatIP init failed — trying hnswlib")
                self._faiss = None

        hnswlib = _try_hnswlib()
        if hnswlib is not None:
            try:
                idx = hnswlib.Index(space="cosine", dim=self._dim)
                idx.init_index(
                    max_elements=self._max_elements, ef_construction=200, M=16,
                )
                idx.set_ef(50)
                self._hnsw = idx
                self._backend = "hnswlib"
                return
            except Exception:  # noqa: BLE001
                logger.warning("hnswlib init failed — trying numpy brute-force")
                self._hnsw = None

        np = _try_numpy()
        if np is not None:
            self._np = np
            self._backend = "numpy"
        else:
            logger.info("No vector backend available — using pure-Python cosine")

    @property
    def backend(self) -> str:
        """Active backend: ``faiss`` | ``hnswlib`` | ``numpy`` | ``python``."""
        return self._backend

    @property
    def count(self) -> int:
        """Number of vectors currently indexed."""
        return len(self._ids)

    # -- Add -------------------------------------------------------------------

    def add(self, fact_id: str, embedding: list[float]) -> None:
        """Add a fact embedding. Never raises — backend errors degrade."""
        vec = _l2_normalise(embedding)
        int_id = len(self._ids)

        if self._backend == "faiss" and self._faiss is not None:
            try:
                self._faiss.add(self._np.array([vec], dtype="float32"))
            except Exception:  # noqa: BLE001
                logger.warning("faiss add failed for %s — mirrored row kept", fact_id)
        elif self._backend == "hnswlib" and self._hnsw is not None:
            try:
                if int_id >= self._max_elements:
                    self._max_elements *= 2
                    self._hnsw.resize_index(self._max_elements)
                self._hnsw.add_items([vec], [int_id])
            except Exception:  # noqa: BLE001
                logger.warning("hnswlib add failed for %s — mirrored row kept", fact_id)

        self._ids.append(fact_id)
        self._vectors.append(vec)

    def add_texts(self, fact_ids: list[str], texts: list[str]) -> int:
        """Encode *texts* and add them under *fact_ids*. Returns count added."""
        embeddings = self._encode(texts)
        if embeddings is None:
            return 0
        added = 0
        for fid, emb in zip(fact_ids, embeddings):
            self.add(fid, emb)
            added += 1
        return added

    # -- Query -----------------------------------------------------------------

    def query(self, embedding: list[float], k: int) -> list[tuple[str, float]]:
        """Return ``[(fact_id, cosine_sim), ...]`` for the top-k nearest."""
        k = min(k, len(self._ids))
        if k <= 0 or not embedding:
            return []
        q = _l2_normalise(embedding)

        if self._backend == "faiss" and self._faiss is not None:
            try:
                return self._query_faiss(q, k)
            except Exception:  # noqa: BLE001
                logger.warning("faiss query failed — falling back to brute-force")
        if self._backend == "hnswlib" and self._hnsw is not None:
            try:
                return self._query_hnsw(q, k)
            except Exception:  # noqa: BLE001
                logger.warning("hnswlib query failed — falling back to brute-force")
        return self._query_brute_force(q, k)

    def query_text(self, text: str, k: int) -> list[tuple[str, float]]:
        """Encode *text* and return its top-k nearest neighbours."""
        embeddings = self._encode([text])
        if not embeddings:
            return []
        return self.query(embeddings[0], k)

    def _query_faiss(self, q: list[float], k: int) -> list[tuple[str, float]]:
        distances, indices = self._faiss.search(self._np.array([q], dtype="float32"), k)
        results = [
            (self._ids[int(i)], float(d))
            for d, i in zip(distances[0], indices[0])
            if 0 <= int(i) < len(self._ids)
        ]
        results.sort(key=lambda x: -x[1])
        return results

    def _query_hnsw(self, q: list[float], k: int) -> list[tuple[str, float]]:
        labels, distances = self._hnsw.knn_query([q], k=k)
        results = [
            (self._ids[int(label)], 1.0 - float(dist))  # cosine space → 1 - sim
            for label, dist in zip(labels[0], distances[0])
            if 0 <= int(label) < len(self._ids)
        ]
        results.sort(key=lambda x: -x[1])
        return results

    def _query_brute_force(self, q: list[float], k: int) -> list[tuple[str, float]]:
        scored: list[tuple[str, float]] = []
        if self._np is not None and self._vectors:
            matrix = self._np.array(self._vectors, dtype="float32")
            sims = matrix @ self._np.array(q, dtype="float32")
            scored = [(fid, float(s)) for fid, s in zip(self._ids, sims)]
        else:
            for fid, vec in zip(self._ids, self._vectors):
                # Rows and query are L2-normalised, so dot == cosine.
                scored.append((fid, sum(x * y for x, y in zip(q, vec))))
        scored.sort(key=lambda x: -x[1])
        return scored[:k]

    # -- Encoding ---------------------------------------------------------------

    def _encode(self, texts: list[str]) -> list[list[float]] | None:
        if self._encoder is not None:
            try:
                return [list(map(float, emb)) for emb in self._encoder(list(texts))]
            except Exception as exc:  # noqa: BLE001
                logger.warning("VectorIndex encoder failed: %s", exc)
                return None
        return encode_texts(list(texts))
