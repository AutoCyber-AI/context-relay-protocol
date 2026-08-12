# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Tests for the Stage 3 NER extractor (dslim/bert-base-NER default).

All ML dependencies are mocked — no network, no model downloads.  Follows
the ``sys.modules`` fake pattern from ``tests/test_safety_wiring.py``.
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

import pytest

import crp.extraction.stage3_ner as stage3_ner
from crp.extraction.stage3_ner import DEFAULT_NER_MODEL, NERExtractor
from crp.extraction.types import Fact

SAMPLE_TEXT = "Constantinos founded AutoCyber AI in Sydney"

# bert-base-NER output with aggregation_strategy="simple"
_BERT_ENTITIES = [
    {"entity_group": "PER", "score": 0.9981, "word": "Constantinos", "start": 0, "end": 12},
    {"entity_group": "ORG", "score": 0.9945, "word": "AutoCyber AI", "start": 21, "end": 33},
    {"entity_group": "LOC", "score": 0.9967, "word": "Sydney", "start": 37, "end": 43},
]


def _bert_pipe(text: str, **kwargs):
    return list(_BERT_ENTITIES)


def _fake_transformers(monkeypatch, pipe_callable) -> MagicMock:
    """Install fake ``transformers``/``torch`` modules wrapping ``pipe_callable``."""
    fake_tf = MagicMock()
    fake_tf.pipeline.return_value = pipe_callable
    monkeypatch.setitem(sys.modules, "transformers", fake_tf)
    monkeypatch.setitem(sys.modules, "torch", MagicMock())
    return fake_tf


def _fake_spacy(monkeypatch, ents) -> MagicMock:
    """Install a fake ``spacy`` module whose nlp() returns *ents* as doc.ents."""
    fake = MagicMock()
    doc = MagicMock()
    doc.ents = ents
    fake.load.return_value = lambda text: doc
    monkeypatch.setitem(sys.modules, "spacy", fake)
    return fake


def _spacy_ent(text: str, label: str, start: int, end: int) -> MagicMock:
    ent = MagicMock()
    ent.text = text
    ent.label_ = label
    ent.start_char = start
    ent.end_char = end
    return ent


@pytest.fixture(autouse=True)
def _clean_ner_state(monkeypatch):
    """Isolate env, model-cache probe, and the shared pipeline cache."""
    monkeypatch.delenv("CRP_NER_MODEL", raising=False)
    # Pretend every model is cached so no socket/cache probe runs in tests.
    monkeypatch.setattr(stage3_ner, "_model_cached", lambda model_id: True)
    stage3_ner._PIPELINE_CACHE.clear()
    yield
    stage3_ner._PIPELINE_CACHE.clear()


# ---------------------------------------------------------------------------
# Default bert-base-NER backend
# ---------------------------------------------------------------------------

def test_bert_default_produces_expected_fact_schema(monkeypatch) -> None:
    _fake_transformers(monkeypatch, _bert_pipe)

    ext = NERExtractor()
    facts = ext.extract(SAMPLE_TEXT, source_window_id="w1")

    assert len(facts) == 3
    by_text = {f.text: f for f in facts}
    assert set(by_text) == {"Constantinos", "AutoCyber AI", "Sydney"}

    # PER/ORG/LOC mapped onto the pipeline category vocabulary
    assert by_text["Constantinos"].category == "person"
    assert by_text["AutoCyber AI"].category == "organization"
    assert by_text["Sydney"].category == "location"

    for fact in facts:
        # Same contract as the GLiNER stage
        assert fact.extraction_stage == 3
        assert fact.source_window_id == "w1"
        assert 0.65 <= fact.confidence <= 0.85
        label, start, end = (
            fact.metadata["label"],
            fact.metadata["span"][0],
            fact.metadata["span"][1],
        )
        assert label in {"PER", "ORG", "LOC"}
        assert SAMPLE_TEXT[start:end] == fact.text
        assert fact.metadata["ner_score"] == pytest.approx(
            next(e["score"] for e in _BERT_ENTITIES if e["word"] == fact.text), abs=1e-4,
        )
        assert fact.metadata["ner_backend"] == "transformers"
        assert fact.metadata["ner_model"] == DEFAULT_NER_MODEL


def test_bert_pipeline_called_with_default_model_and_aggregation(monkeypatch) -> None:
    fake_tf = _fake_transformers(monkeypatch, _bert_pipe)

    ext = NERExtractor()
    ext.extract(SAMPLE_TEXT)

    fake_tf.pipeline.assert_called_once_with(
        "ner", model="dslim/bert-base-NER", aggregation_strategy="simple",
    )


def test_confidence_clamped_and_threshold_filters(monkeypatch) -> None:
    def pipe(text: str, **kwargs):
        return [
            {"entity_group": "PER", "score": 0.99, "word": "Ada", "start": 0, "end": 3},
            {"entity_group": "ORG", "score": 0.30, "word": "Acme", "start": 4, "end": 8},
        ]

    _fake_transformers(monkeypatch, pipe)
    ext = NERExtractor()

    facts = ext.extract("Ada Acme", threshold=0.5)
    assert len(facts) == 1
    assert facts[0].text == "Ada"
    assert facts[0].confidence == 0.85  # clamped from 0.99


def test_labels_argument_ignored_for_bert(monkeypatch) -> None:
    _fake_transformers(monkeypatch, _bert_pipe)
    ext = NERExtractor()
    # bert-base-NER has a fixed label set — labels must not break anything
    facts = ext.extract(SAMPLE_TEXT, labels=["custom", "labels"])
    assert len(facts) == 3


# ---------------------------------------------------------------------------
# Fallback chain
# ---------------------------------------------------------------------------

def test_import_error_falls_back_without_failing(monkeypatch) -> None:
    # transformers, torch and spacy all "not installed"
    for name in ("transformers", "torch", "spacy"):
        monkeypatch.setitem(sys.modules, name, None)

    ext = NERExtractor()
    assert ext.extract(SAMPLE_TEXT) == []
    assert not ext.is_available  # never raises


def test_pipeline_load_failure_degrades_to_spacy(monkeypatch) -> None:
    fake_tf = MagicMock()
    fake_tf.pipeline.side_effect = RuntimeError("model exploded")
    monkeypatch.setitem(sys.modules, "transformers", fake_tf)
    monkeypatch.setitem(sys.modules, "torch", MagicMock())
    _fake_spacy(monkeypatch, [_spacy_ent("Sydney", "GPE", 37, 43)])

    ext = NERExtractor()
    facts = ext.extract(SAMPLE_TEXT)

    assert len(facts) == 1
    assert facts[0].text == "Sydney"
    assert facts[0].category == "location"  # GPE mapped
    assert facts[0].metadata["ner_backend"] == "spacy"


def test_offline_uncached_model_degrades_gracefully(monkeypatch) -> None:
    def _must_not_run(task, **kwargs):
        raise AssertionError("pipeline must not be called when offline and uncached")

    _fake_transformers(monkeypatch, _must_not_run)
    monkeypatch.setattr(stage3_ner, "_model_cached", lambda model_id: False)
    monkeypatch.setattr(stage3_ner, "_hub_reachable", lambda: False)
    _fake_spacy(monkeypatch, [_spacy_ent("Sydney", "LOC", 37, 43)])

    ext = NERExtractor()
    facts = ext.extract(SAMPLE_TEXT)
    assert [f.text for f in facts] == ["Sydney"]
    assert facts[0].metadata["ner_backend"] == "spacy"


def test_spacy_fallback_maps_labels(monkeypatch) -> None:
    for name in ("transformers", "torch"):
        monkeypatch.setitem(sys.modules, name, None)
    _fake_spacy(monkeypatch, [
        _spacy_ent("Constantinos", "PERSON", 0, 12),
        _spacy_ent("AutoCyber AI", "ORG", 21, 33),
        _spacy_ent("Sydney", "GPE", 37, 43),
    ])

    ext = NERExtractor()
    facts = ext.extract(SAMPLE_TEXT)

    assert [f.category for f in facts] == ["person", "organization", "location"]
    for fact in facts:
        assert fact.extraction_stage == 3
        assert fact.confidence == 0.75  # spaCy has no per-entity score
        assert fact.metadata["ner_backend"] == "spacy"
        start, end = fact.metadata["span"]
        assert SAMPLE_TEXT[start:end] == fact.text


def test_spacy_missing_means_unavailable_not_error(monkeypatch) -> None:
    for name in ("transformers", "torch", "spacy"):
        monkeypatch.setitem(sys.modules, name, None)

    ext = NERExtractor()
    assert ext.extract(SAMPLE_TEXT) == []


# ---------------------------------------------------------------------------
# CRP_NER_MODEL override
# ---------------------------------------------------------------------------

def test_gliner_opt_in_delegates_with_labels(monkeypatch) -> None:
    import crp.extraction.stage3_gliner as gliner_mod

    monkeypatch.setenv("CRP_NER_MODEL", "urchade/gliner_base")
    sentinel = Fact(text="x", category="entity", confidence=0.7, extraction_stage=3)
    calls: dict = {}

    monkeypatch.setattr(
        gliner_mod.GLiNERExtractor, "_ensure_model", lambda self: object(),
    )

    def _fake_extract(self, text, labels=None, source_window_id="", threshold=0.5):
        calls["labels"] = labels
        calls["text"] = text
        return [sentinel]

    monkeypatch.setattr(gliner_mod.GLiNERExtractor, "extract", _fake_extract)

    ext = NERExtractor()
    facts = ext.extract(SAMPLE_TEXT, labels=["person", "company"])

    assert facts == [sentinel]
    assert calls["labels"] == ["person", "company"]
    assert ext._backend == "gliner"


def test_env_override_uses_custom_transformers_model(monkeypatch) -> None:
    fake_tf = _fake_transformers(monkeypatch, _bert_pipe)
    monkeypatch.setenv("CRP_NER_MODEL", "custom/ner-9b")

    ext = NERExtractor()
    ext.extract(SAMPLE_TEXT)

    fake_tf.pipeline.assert_called_once_with(
        "ner", model="custom/ner-9b", aggregation_strategy="simple",
    )


# ---------------------------------------------------------------------------
# Lifecycle (mirrors the GLiNER extractor contract)
# ---------------------------------------------------------------------------

def test_unavailable_returns_empty() -> None:
    ext = NERExtractor()
    ext._available = False
    assert ext.extract(SAMPLE_TEXT) == []


def test_tick_idle_unloads_shared_pipeline(monkeypatch) -> None:
    _fake_transformers(monkeypatch, _bert_pipe)
    ext = NERExtractor(idle_limit=3)
    ext.extract(SAMPLE_TEXT)
    assert DEFAULT_NER_MODEL in stage3_ner._PIPELINE_CACHE

    for _ in range(3):
        ext.tick_idle()
    assert DEFAULT_NER_MODEL not in stage3_ner._PIPELINE_CACHE


def test_shared_pipeline_cache_reused_across_instances(monkeypatch) -> None:
    fake_tf = _fake_transformers(monkeypatch, _bert_pipe)
    NERExtractor().extract(SAMPLE_TEXT)
    NERExtractor().extract(SAMPLE_TEXT)
    # Second instance reuses the cached pipeline — no reload.
    assert fake_tf.pipeline.call_count == 1


# ---------------------------------------------------------------------------
# Pipeline integration (Stage 3 wired as the default)
# ---------------------------------------------------------------------------

def test_extraction_pipeline_runs_ner_stage_by_default(monkeypatch) -> None:
    _fake_transformers(monkeypatch, _bert_pipe)

    from crp.extraction.pipeline import ExtractionPipeline

    pipeline = ExtractionPipeline(enable_stage_4=False, enable_stage_5=False)
    result = pipeline.extract(SAMPLE_TEXT)

    assert 3 in result.stages_run
    s3_categories = {f.category for f in result.facts if f.extraction_stage == 3}
    assert {"person", "organization", "location"} <= s3_categories


# ---------------------------------------------------------------------------
# Adaptive latency budget (§7.14 overhead invariant)
# ---------------------------------------------------------------------------

def test_ner_budget_strikes_disable_stage3(monkeypatch) -> None:
    """Three over-budget model calls degrade Stage 3 to rule-based extraction."""
    import time as _time

    def _slow_pipe(text: str, **kwargs):
        _time.sleep(0.01)
        return list(_BERT_ENTITIES)

    _fake_transformers(monkeypatch, _slow_pipe)
    monkeypatch.setenv("CRP_NER_BUDGET_MS", "1")  # 1ms — every call is a strike
    stage3_ner._PIPELINE_CACHE.clear()

    ext = NERExtractor()
    for _ in range(3):
        ext.extract(SAMPLE_TEXT)

    # After 3 strikes the backend is disabled and extraction returns [].
    assert ext._available is False
    assert ext.extract(SAMPLE_TEXT) == []
