# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Tests for the CKF vector index (faiss-first default backend).

All heavy dependencies (faiss, sentence-transformers) are faked via
``sys.modules`` — no network, no model downloads.  Follows the pattern from
``tests/test_ml_downloader.py`` and ``tests/test_safety_wiring.py``.
"""

from __future__ import annotations

import importlib.util
import sys
import types
from unittest.mock import MagicMock

import pytest

import crp.ckf.vector_index as vector_index
from crp.ckf.vector_index import VectorIndex


@pytest.fixture(autouse=True)
def _clean_encoder(monkeypatch):
    """Isolate the encoder singleton and env between tests."""
    monkeypatch.delenv("CRP_EMBEDDING_MODEL", raising=False)
    vector_index.reset_encoder()
    yield
    vector_index.reset_encoder()


def _block_faiss_hnswlib(monkeypatch) -> None:
    """Make faiss and hnswlib 'not installed' (numpy stays available)."""
    monkeypatch.setitem(sys.modules, "faiss", None)
    monkeypatch.setitem(sys.modules, "hnswlib", None)


# ---------------------------------------------------------------------------
# Backend selection
# ---------------------------------------------------------------------------

def test_backend_falls_back_to_numpy(monkeypatch) -> None:
    _block_faiss_hnswlib(monkeypatch)
    idx = VectorIndex(dim=3)
    assert idx.backend == "numpy"


def test_backend_falls_back_to_pure_python(monkeypatch) -> None:
    _block_faiss_hnswlib(monkeypatch)
    monkeypatch.setitem(sys.modules, "numpy", None)
    idx = VectorIndex(dim=3)
    assert idx.backend == "python"


def test_backend_prefers_faiss(monkeypatch) -> None:
    _fake_faiss(monkeypatch)
    idx = VectorIndex(dim=3)
    assert idx.backend == "faiss"


def test_backend_hnswlib_when_faiss_missing(monkeypatch) -> None:
    if importlib.util.find_spec("hnswlib") is None:
        pytest.skip("hnswlib not installed")
    monkeypatch.setitem(sys.modules, "faiss", None)
    idx = VectorIndex(dim=3)
    assert idx.backend == "hnswlib"


# ---------------------------------------------------------------------------
# Add / search correctness
# ---------------------------------------------------------------------------

_VECTORS = {
    "apple": [1.0, 0.0, 0.0],
    "apple-ish": [0.9, 0.1, 0.0],
    "banana": [0.0, 1.0, 0.0],
}


def _assert_nearest_first(results) -> None:
    assert results[0][0] == "apple"
    assert results[0][1] == pytest.approx(1.0, abs=1e-5)
    assert results[1][0] == "apple-ish"
    assert results[1][1] == pytest.approx(0.9939, abs=1e-3)


def test_add_and_query_numpy_fallback(monkeypatch) -> None:
    _block_faiss_hnswlib(monkeypatch)
    idx = VectorIndex(dim=3)
    for fid, vec in _VECTORS.items():
        idx.add(fid, vec)

    assert idx.count == 3
    results = idx.query([1.0, 0.0, 0.0], k=2)
    _assert_nearest_first(results)


def test_add_and_query_pure_python(monkeypatch) -> None:
    _block_faiss_hnswlib(monkeypatch)
    monkeypatch.setitem(sys.modules, "numpy", None)
    idx = VectorIndex(dim=3)
    for fid, vec in _VECTORS.items():
        idx.add(fid, vec)

    results = idx.query([1.0, 0.0, 0.0], k=2)
    _assert_nearest_first(results)


def test_query_normalises_vectors(monkeypatch) -> None:
    """Cosine must hold for unnormalised inputs: [3,0,0] ~ [1,0,0] == 1.0."""
    _block_faiss_hnswlib(monkeypatch)
    idx = VectorIndex(dim=3)
    idx.add("x", [3.0, 0.0, 0.0])
    idx.add("y", [1.0, 1.0, 0.0])

    results = idx.query([5.0, 0.0, 0.0], k=2)
    assert results[0] == ("x", pytest.approx(1.0, abs=1e-5))
    assert results[1][1] == pytest.approx(2**-0.5, abs=1e-4)


def test_query_empty_index_returns_empty(monkeypatch) -> None:
    _block_faiss_hnswlib(monkeypatch)
    idx = VectorIndex(dim=3)
    assert idx.query([1.0, 0.0, 0.0], k=5) == []


# ---------------------------------------------------------------------------
# faiss backend (faked — validates the IndexFlatIP code path)
# ---------------------------------------------------------------------------

class _FakeIndexFlatIP:
    """Minimal stand-in for faiss.IndexFlatIP backed by real numpy math."""

    def __init__(self, dim: int) -> None:
        self.dim = dim
        self.vecs: list[list[float]] = []

    def add(self, arr) -> None:
        self.vecs.extend([list(map(float, row)) for row in arr.tolist()])

    def search(self, q, k):
        import numpy as np

        qv = np.array(q[0], dtype="float32")
        sims = [float(np.dot(qv, np.array(v, dtype="float32"))) for v in self.vecs]
        order = sorted(range(len(sims)), key=lambda i: -sims[i])[:k]
        distances = np.array([[sims[i] for i in order]], dtype="float32")
        indices = np.array([order], dtype="int64")
        return distances, indices


def _fake_faiss(monkeypatch) -> types.SimpleNamespace:
    fake = types.SimpleNamespace(IndexFlatIP=_FakeIndexFlatIP)
    monkeypatch.setitem(sys.modules, "faiss", fake)
    return fake


def test_faiss_path_add_and_query(monkeypatch) -> None:
    _fake_faiss(monkeypatch)
    idx = VectorIndex(dim=3)
    for fid, vec in _VECTORS.items():
        idx.add(fid, vec)

    assert idx.backend == "faiss"
    results = idx.query([1.0, 0.0, 0.0], k=2)
    _assert_nearest_first(results)

    # Vectors must be L2-normalised before hitting IndexFlatIP
    stored = idx._faiss.vecs[0]
    assert stored == pytest.approx([1.0, 0.0, 0.0])


def test_hnswlib_path_add_and_query(monkeypatch) -> None:
    if importlib.util.find_spec("hnswlib") is None:
        pytest.skip("hnswlib not installed")
    monkeypatch.setitem(sys.modules, "faiss", None)
    idx = VectorIndex(dim=3)
    for fid, vec in _VECTORS.items():
        idx.add(fid, vec)

    results = idx.query([1.0, 0.0, 0.0], k=2)
    assert results[0][0] == "apple"
    assert results[0][1] == pytest.approx(1.0, abs=1e-4)


# ---------------------------------------------------------------------------
# Embedding (fake encoder — no model download)
# ---------------------------------------------------------------------------

def _fake_encoder(texts: list[str]) -> list[list[float]]:
    return [[1.0, 0.0, 0.0] if "apple" in t else [0.0, 1.0, 0.0] for t in texts]


def test_add_texts_and_query_text_with_fake_encoder(monkeypatch) -> None:
    _block_faiss_hnswlib(monkeypatch)
    idx = VectorIndex(dim=3, encoder=_fake_encoder)

    added = idx.add_texts(["f1", "f2"], ["apple fruit", "banana fruit"])
    assert added == 2

    results = idx.query_text("apple smoothie", k=1)
    assert results == [("f1", pytest.approx(1.0))]


def test_encoder_failure_never_raises(monkeypatch) -> None:
    def _boom(texts):
        raise RuntimeError("encoder exploded")

    _block_faiss_hnswlib(monkeypatch)
    idx = VectorIndex(dim=3, encoder=_boom)
    assert idx.add_texts(["f1"], ["text"]) == 0
    assert idx.query_text("text", k=1) == []


# ---------------------------------------------------------------------------
# Default sentence-transformers singleton (mocked)
# ---------------------------------------------------------------------------

class _FakeSentenceTransformer:
    last_model_id: str | None = None
    init_count: int = 0

    def __init__(self, model_id: str) -> None:
        type(self).last_model_id = model_id
        type(self).init_count += 1

    def encode(self, texts, convert_to_numpy=True):
        return [[1.0, 0.0] for _ in texts]


def _fake_sentence_transformers(monkeypatch) -> types.SimpleNamespace:
    _FakeSentenceTransformer.last_model_id = None
    _FakeSentenceTransformer.init_count = 0
    fake = types.SimpleNamespace(SentenceTransformer=_FakeSentenceTransformer)
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake)
    return fake


def test_default_encoder_uses_manifest_model_id(monkeypatch) -> None:
    _fake_sentence_transformers(monkeypatch)

    model = vector_index.get_encoder()
    assert model is not None
    assert _FakeSentenceTransformer.last_model_id == "sentence-transformers/all-MiniLM-L6-v2"
    assert vector_index.active_embedding_model_id() == "sentence-transformers/all-MiniLM-L6-v2"

    embeddings = vector_index.encode_texts(["hello", "world"])
    assert embeddings == [[1.0, 0.0], [1.0, 0.0]]

    # Singleton: a second call must not reload the model
    vector_index.get_encoder()
    assert _FakeSentenceTransformer.init_count == 1


def test_embedding_model_env_override(monkeypatch) -> None:
    _fake_sentence_transformers(monkeypatch)
    monkeypatch.setenv("CRP_EMBEDDING_MODEL", "custom/embed-9b")

    assert vector_index.resolve_embedding_model_id() == "custom/embed-9b"
    vector_index.get_encoder()
    assert _FakeSentenceTransformer.last_model_id == "custom/embed-9b"
    assert vector_index.active_embedding_model_id() == "custom/embed-9b"


def test_encoder_unavailable_degrades_gracefully(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "sentence_transformers", None)
    _block_faiss_hnswlib(monkeypatch)

    assert vector_index.get_encoder() is None
    assert vector_index.get_encoder() is None  # cached failure, no retry storm
    assert vector_index.encode_texts(["x"]) is None
    assert vector_index.active_embedding_model_id() is None

    idx = VectorIndex(dim=2)
    assert idx.add_texts(["f1"], ["text"]) == 0
    assert idx.query_text("text", k=1) == []


def test_index_records_embedding_model_id(monkeypatch) -> None:
    _block_faiss_hnswlib(monkeypatch)
    idx = VectorIndex(dim=3)
    # Manifest default recorded even before the encoder is loaded (Invariant 5)
    assert idx.embedding_model_id == "sentence-transformers/all-MiniLM-L6-v2"


# ---------------------------------------------------------------------------
# CKF fabric integration
# ---------------------------------------------------------------------------

def test_ckf_fabric_routes_semantic_through_vector_index(monkeypatch) -> None:
    _block_faiss_hnswlib(monkeypatch)
    monkeypatch.setattr("crp.ckf.semantic.ANN_THRESHOLD", 3)

    from crp.ckf.fabric import CKFConfig, ContextualKnowledgeFabric
    from crp.extraction.types import Fact

    ckf = ContextualKnowledgeFabric(CKFConfig(hnsw_threshold=3, community_detect_enabled=False))
    texts = {
        "f-apple": "apples are sweet fruit",
        "f-apple2": "apple pie recipe",
        "f-banana": "bananas are yellow",
        "f-cherry": "cherries are red",
        "f-date": "dates grow on palms",
    }
    vecs = {
        "f-apple": [1.0, 0.0, 0.0],
        "f-apple2": [0.98, 0.02, 0.0],
        "f-banana": [0.0, 1.0, 0.0],
        "f-cherry": [0.0, 0.0, 1.0],
        "f-date": [0.0, 0.5, 0.5],
    }
    facts = [Fact(id=fid, text=text, category="test", confidence=0.9)
             for fid, text in texts.items()]
    ckf.store(facts, window_id="w1")
    for fid, vec in vecs.items():
        ckf._warm._facts[fid].embedding = vec

    merged = ckf.retrieve(query_embedding=[1.0, 0.0, 0.0], modes=["semantic"], budget=5)

    assert ckf._vector_index is not None
    assert ckf._vector_index.backend == "numpy"
    assert ckf.health().hnsw_active is True
    assert merged.facts, "semantic mode must return facts"
    assert merged.facts[0].fact.id == "f-apple"
