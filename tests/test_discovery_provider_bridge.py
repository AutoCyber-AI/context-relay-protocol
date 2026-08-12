"""Tests for discovery -> provider adapter bridge."""

from __future__ import annotations

from crp.providers.discovery import DetectedModel, RuntimeKind, ModelState


class TestDetectedModelToProvider:
    def test_ollama_model_to_provider(self):
        model = DetectedModel(
            id="llama3.1",
            runtime=RuntimeKind.OLLAMA,
            endpoint="http://127.0.0.1:11434",
            state=ModelState.LOADED,
            loaded_context_length=8192,
        )
        provider = model.to_provider()
        assert provider is not None
        assert provider.model_name == "llama3.1"
        assert provider.supports_tools() is True
        assert provider.context_window_size() == 8192

    def test_llamacpp_model_to_provider(self):
        model = DetectedModel(
            id="llama-3-8b",
            runtime=RuntimeKind.LLAMA_CPP,
            endpoint="http://127.0.0.1:8080",
            state=ModelState.LOADED,
            loaded_context_length=4096,
        )
        provider = model.to_provider()
        assert provider is not None
        assert provider.supports_tools() is True
        assert provider.context_window_size() == 4096

    def test_lm_studio_model_to_provider(self):
        model = DetectedModel(
            id="qwen2.5-7b",
            runtime=RuntimeKind.LM_STUDIO,
            endpoint="http://127.0.0.1:1234",
            state=ModelState.LOADED,
            loaded_context_length=8192,
        )
        provider = model.to_provider()
        assert provider is not None
        assert provider.model_name == "qwen2.5-7b"
        assert provider.supports_tools() is True

    def test_non_llm_returns_none(self):
        model = DetectedModel(
            id="all-minilm",
            runtime=RuntimeKind.OLLAMA,
            endpoint="http://127.0.0.1:11434",
            model_type="embeddings",
        )
        assert model.to_provider() is None
