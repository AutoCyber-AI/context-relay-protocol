# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Coverage tests for ``crp.providers.discovery`` — local LLM probing (§6.2).

HTTP probing is mocked by monkeypatching the module-level ``_get_json`` /
``_post_json`` helpers, following the style of
``tests/test_discovery_provider_bridge.py``.  No real network is touched.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from crp.providers import discovery
from crp.providers.discovery import (
    DEFAULT_ENDPOINTS,
    DetectedModel,
    DetectedRuntime,
    DiscoveryReport,
    ModelState,
    RuntimeKind,
    _looks_like_reasoning,
    _looks_tool_capable,
    _parse_lmstudio_native,
    _parse_ollama_tags,
    _parse_openai_models,
    _probe,
    _probe_lmstudio,
    _probe_ollama,
    _probe_openai_compatible,
    discover_local_llms,
)

# ── Heuristics ──────────────────────────────────────────────────────────


def test_reasoning_and_tool_markers() -> None:
    assert _looks_like_reasoning("qwen3-4b-instruct")
    assert _looks_like_reasoning("deepseek-r1-distill")
    assert not _looks_like_reasoning("llama-3.1-8b")
    assert _looks_tool_capable("llama-3-8b-instruct")
    assert _looks_tool_capable("mistral-7b")
    assert not _looks_tool_capable("olmo-7b")


# ── Parsers ─────────────────────────────────────────────────────────────


def test_parse_lmstudio_native_full() -> None:
    data = {
        "data": [
            {
                "id": "qwen3-4b",
                "arch": "qwen3",
                "capabilities": ["tool_use", "reasoning"],
                "state": "loaded",
                "type": "llm",
                "publisher": "Qwen",
                "quantization": "Q4_K_M",
                "max_context_length": 40960,
                "loaded_context_length": 8192,
            },
            {
                "id": "clip-vit",
                "state": "not-loaded",
                "type": "vlm",
                "capabilities": ["vision"],
            },
            {"not_a_dict": True},
            {"id": "", "state": "whatever"},
        ],
    }
    models = _parse_lmstudio_native(data, "http://127.0.0.1:1234")
    assert len(models) == 4  # blank ids are kept (unlike the OpenAI parser)
    m0 = models[0]
    assert m0.state is ModelState.LOADED
    assert m0.supports_tools is True
    assert m0.is_reasoning_model is True
    assert m0.quantization == "Q4_K_M"
    assert m0.context_utilisation == 0.2
    m1 = models[1]
    assert m1.state is ModelState.NOT_LOADED
    assert m1.is_vision_model is True
    assert m1.supports_tools is False  # vlm never advertises tools
    assert models[2].state is ModelState.UNKNOWN


def test_parse_lmstudio_native_empty() -> None:
    assert _parse_lmstudio_native({}, "e") == []
    assert _parse_lmstudio_native(None, "e") == []


def test_parse_openai_models_skips_blank_ids() -> None:
    data = {"data": [{"id": "gpt-oss-20b"}, {"id": ""}, {"no_id": 1}]}
    models = _parse_openai_models(data, "http://x", RuntimeKind.OPENAI_COMPATIBLE)
    assert [m.id for m in models] == ["gpt-oss-20b"]
    assert models[0].runtime is RuntimeKind.OPENAI_COMPATIBLE
    assert models[0].is_reasoning_model is True  # "gpt-oss" marker


def test_parse_ollama_tags_with_show_enrichment(monkeypatch) -> None:
    def _fake_post(url, payload, *, timeout):
        return {
            "capabilities": ["tools", "vision"],
            "model_info": {
                f"{payload['model']}.context_length": 131072,
                "other.key": 1,
            },
        }

    monkeypatch.setattr(discovery, "_post_json", _fake_post)
    data = {"models": [
        {"name": "llama3.1", "details": {"family": "llama", "quantization_level": "Q4_0"}},
        {"model": "qwen2.5:7b"},  # alternate key
        {"details": {}},          # no name — skipped
    ]}
    models = _parse_ollama_tags(data, "http://127.0.0.1:11434", timeout=1.0)
    assert [m.id for m in models] == ["llama3.1", "qwen2.5:7b"]
    assert models[0].max_context_length == 131072
    assert models[1].max_context_length == 131072
    assert models[0].supports_tools is True
    assert models[0].is_vision_model is True
    assert models[1].architecture == ""


def test_parse_ollama_tags_show_failure_tolerated(monkeypatch) -> None:
    monkeypatch.setattr(discovery, "_post_json", lambda *a, **k: None)
    models = _parse_ollama_tags(
        {"models": [{"name": "mistral"}]}, "http://e", timeout=1.0,
    )
    assert len(models) == 1
    assert models[0].max_context_length is None


# ── Probers ─────────────────────────────────────────────────────────────


def test_probe_lmstudio_prefers_native(monkeypatch) -> None:
    calls: list[str] = []

    def _fake_get(url, *, timeout):
        calls.append(url)
        if url.endswith("/api/v0/models"):
            return {"data": [{"id": "m1", "state": "loaded"}]}
        return None

    monkeypatch.setattr(discovery, "_get_json", _fake_get)
    rt = _probe_lmstudio("http://127.0.0.1:1234", timeout=1.0)
    assert rt.reachable is True
    assert rt.models[0].id == "m1"
    assert not any(url.endswith("/v1/models") for url in calls)


def test_probe_lmstudio_openai_fallback(monkeypatch) -> None:
    def _fake_get(url, *, timeout):
        if url.endswith("/v1/models"):
            return {"data": [{"id": "fallback-model"}]}
        return None

    monkeypatch.setattr(discovery, "_get_json", _fake_get)
    rt = _probe_lmstudio("http://127.0.0.1:1234", timeout=1.0)
    assert rt.reachable is True
    assert rt.models[0].id == "fallback-model"


def test_probe_lmstudio_unreachable(monkeypatch) -> None:
    monkeypatch.setattr(discovery, "_get_json", lambda *a, **k: None)
    rt = _probe_lmstudio("http://127.0.0.1:1234", timeout=1.0)
    assert rt.reachable is False
    assert rt.error


def test_probe_ollama_marks_loaded(monkeypatch) -> None:
    def _fake_get(url, *, timeout):
        if url.endswith("/api/tags"):
            return {"models": [{"name": "a"}, {"name": "b"}]}
        if url.endswith("/api/ps"):
            return {"models": [{"name": "a", "model": "a"}]}
        return None

    monkeypatch.setattr(discovery, "_get_json", _fake_get)
    monkeypatch.setattr(discovery, "_post_json", lambda *a, **k: None)
    rt = _probe_ollama("http://127.0.0.1:11434", timeout=1.0)
    assert rt.reachable is True
    states = {m.id: m.state for m in rt.models}
    assert states == {"a": ModelState.LOADED, "b": ModelState.NOT_LOADED}


def test_probe_ollama_unreachable(monkeypatch) -> None:
    monkeypatch.setattr(discovery, "_get_json", lambda *a, **k: None)
    rt = _probe_ollama("http://127.0.0.1:11434", timeout=1.0)
    assert rt.reachable is False
    assert rt.error


def test_probe_openai_compatible_with_props(monkeypatch) -> None:
    def _fake_get(url, *, timeout):
        if url.endswith("/v1/models"):
            return {"data": [{"id": "llama-3-8b"}]}
        if url.endswith("/props"):
            return {"default_generation_settings": {"n_ctx": 4096}}
        return None

    monkeypatch.setattr(discovery, "_get_json", _fake_get)
    rt = _probe_openai_compatible(
        "http://127.0.0.1:8080", RuntimeKind.LLAMA_CPP, timeout=1.0,
    )
    assert rt.reachable is True
    assert rt.models[0].state is ModelState.LOADED
    assert rt.models[0].loaded_context_length == 4096


def test_probe_openai_compatible_n_ctx_top_level(monkeypatch) -> None:
    def _fake_get(url, *, timeout):
        if url.endswith("/v1/models"):
            return {"data": [{"id": "m"}]}
        if url.endswith("/props"):
            return {"n_ctx": 2048}
        return None

    monkeypatch.setattr(discovery, "_get_json", _fake_get)
    rt = _probe_openai_compatible(
        "http://x", RuntimeKind.OPENAI_COMPATIBLE, timeout=1.0,
    )
    assert rt.models[0].loaded_context_length == 2048


def test_probe_openai_compatible_unreachable(monkeypatch) -> None:
    monkeypatch.setattr(discovery, "_get_json", lambda *a, **k: None)
    rt = _probe_openai_compatible("http://x", RuntimeKind.OPENAI_COMPATIBLE, timeout=1.0)
    assert rt.reachable is False


def test_probe_dispatch(monkeypatch) -> None:
    monkeypatch.setattr(discovery, "_get_json", lambda *a, **k: None)
    lm = _probe(DEFAULT_ENDPOINTS[0], timeout=1.0)
    assert lm.runtime is RuntimeKind.LM_STUDIO
    ol = _probe(DEFAULT_ENDPOINTS[1], timeout=1.0)
    assert ol.runtime is RuntimeKind.OLLAMA
    lc = _probe(DEFAULT_ENDPOINTS[2], timeout=1.0)
    assert lc.runtime is RuntimeKind.LLAMA_CPP


# ── discover_local_llms ─────────────────────────────────────────────────


def test_discover_all_unreachable(monkeypatch) -> None:
    monkeypatch.setattr(discovery, "_get_json", lambda *a, **k: None)
    report = discover_local_llms(timeout=0.01)
    assert len(report.runtimes) == len(DEFAULT_ENDPOINTS)
    assert not report.any_reachable
    assert report.loaded_models == []
    assert report.primary_model() is None
    # Serialization round-trips.
    doc = report.to_dict()
    assert doc["any_reachable"] is False
    assert doc["model_count"] == 0


def test_discover_with_reachable_runtime(monkeypatch) -> None:
    endpoints = (SimpleNamespace(base_url="http://127.0.0.1:1234", runtime=RuntimeKind.LM_STUDIO),)

    def _fake_get(url, *, timeout):
        return {"data": [{"id": "loaded-model", "state": "loaded", "type": "llm"}]}

    monkeypatch.setattr(discovery, "_get_json", _fake_get)
    report = discover_local_llms(endpoints=endpoints, timeout=0.01)
    assert report.any_reachable
    assert len(report.reachable_runtimes) == 1
    assert report.models[0].id == "loaded-model"
    assert report.loaded_models[0].is_loaded
    assert report.primary_model() is report.models[0]
    doc = report.to_dict()
    assert doc["loaded_count"] == 1


def test_discover_probe_exception_captured(monkeypatch) -> None:
    endpoints = (SimpleNamespace(base_url="http://x", runtime=RuntimeKind.UNKNOWN),)

    def _exploding_probe(endpoint, *, timeout):
        raise RuntimeError("probe exploded")

    monkeypatch.setattr(discovery, "_probe", _exploding_probe)
    report = discover_local_llms(endpoints=endpoints, timeout=0.01)
    assert len(report.runtimes) == 1
    assert report.runtimes[0].reachable is False
    assert "probe exploded" in report.runtimes[0].error


# ── DetectedModel / containers ──────────────────────────────────────────


def test_model_is_loaded_and_utilisation() -> None:
    loaded = DetectedModel(id="m", runtime=RuntimeKind.OLLAMA, endpoint="e", state=ModelState.LOADED)
    assert loaded.is_loaded
    not_loaded = DetectedModel(id="m", runtime=RuntimeKind.OLLAMA, endpoint="e")
    assert not not_loaded.is_loaded
    no_ctx = DetectedModel(id="m", runtime=RuntimeKind.OLLAMA, endpoint="e")
    assert no_ctx.context_utilisation is None
    half = DetectedModel(
        id="m", runtime=RuntimeKind.OLLAMA, endpoint="e",
        max_context_length=8192, loaded_context_length=4096,
    )
    assert half.context_utilisation == 0.5


def test_model_to_provider_openai_compatible() -> None:
    model = DetectedModel(
        id="vllm-model",
        runtime=RuntimeKind.OPENAI_COMPATIBLE,
        endpoint="http://127.0.0.1:8000",
        loaded_context_length=16384,
    )
    provider = model.to_provider()
    assert provider is not None
    assert provider.context_window_size() == 16384


def test_model_to_provider_unknown_runtime() -> None:
    model = DetectedModel(id="m", runtime=RuntimeKind.UNKNOWN, endpoint="e")
    assert model.to_provider() is None


def test_model_to_dict() -> None:
    model = DetectedModel(
        id="m", runtime=RuntimeKind.LM_STUDIO, endpoint="e",
        max_context_length=100, loaded_context_length=25,
    )
    doc = model.to_dict()
    assert doc["runtime"] == "lmstudio"
    assert doc["context_utilisation"] == 0.25
    assert doc["supports_tools"] is False


def test_detected_runtime_to_dict() -> None:
    rt = DetectedRuntime(runtime=RuntimeKind.OLLAMA, base_url="e", reachable=True)
    rt.models.append(DetectedModel(id="m", runtime=RuntimeKind.OLLAMA, endpoint="e"))
    doc = rt.to_dict()
    assert doc["reachable"] is True
    assert len(doc["models"]) == 1


def test_report_primary_model_prefers_loaded_llm() -> None:
    rt = DetectedRuntime(runtime=RuntimeKind.OLLAMA, base_url="e", reachable=True)
    rt.models.append(DetectedModel(
        id="embed", runtime=RuntimeKind.OLLAMA, endpoint="e", model_type="embeddings",
    ))
    rt.models.append(DetectedModel(id="cold", runtime=RuntimeKind.OLLAMA, endpoint="e"))
    rt.models.append(DetectedModel(id="hot", runtime=RuntimeKind.OLLAMA, endpoint="e", state=ModelState.LOADED))
    report = DiscoveryReport(runtimes=[rt])
    assert report.primary_model().id == "hot"
