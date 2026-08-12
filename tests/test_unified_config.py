# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Tests for Unified Configuration and Storage Backends (SPEC-037, SPEC-038)."""

from __future__ import annotations

import pytest

from crp.config import CRPConfig
from crp.config_schema import validate_config
from crp.state.backends import InMemoryBackend, StorageBackend, StorageBackendError


class TestCRPConfig:
    def test_default_values(self) -> None:
        cfg = CRPConfig()
        assert cfg.get("version") == "4"
        assert cfg.get("context.retrieval.min_relevance") == 0.55
        assert cfg.get("context.retrieval.max_hops") == 2

    def test_set_and_get(self) -> None:
        cfg = CRPConfig()
        cfg.set("safety.profile", "strict")
        assert cfg.get("safety.profile") == "strict"

    def test_missing_key_returns_default(self) -> None:
        cfg = CRPConfig()
        assert cfg.get("nonexistent.path", "fallback") == "fallback"

    def test_config_hash(self) -> None:
        cfg = CRPConfig()
        h = cfg.get_config_hash()
        assert len(h) == 32  # blake2b 16 bytes = 32 hex chars

    def test_layer_override(self) -> None:
        cfg = CRPConfig()
        cfg2 = cfg.layer_override({"safety.profile": "medical"})
        assert cfg2.get("safety.profile") == "medical"
        assert cfg.get("safety.profile") == "balanced"  # original unchanged

    def test_roundtrip_dict(self) -> None:
        cfg = CRPConfig()
        cfg.set("safety.profile", "strict")
        d = cfg.to_dict()
        assert d["safety"]["profile"] == "strict"


class TestConfigSchema:
    def test_valid_minimal(self) -> None:
        errors = validate_config({"version": "4"})
        assert len(errors) == 0

    def test_valid_full(self) -> None:
        errors = validate_config({
            "version": "4",
            "model": {"default": "gpt-4o"},
            "safety": {"profile": "strict"},
            "context": {"mode": "auto", "depth": "thorough"},
        })
        assert len(errors) == 0

    def test_invalid_profile(self) -> None:
        errors = validate_config({"safety": {"profile": "invalid"}})
        assert len(errors) == 1
        assert "invalid" in errors[0]

    def test_invalid_min_relevance(self) -> None:
        errors = validate_config({"context": {"retrieval": {"min_relevance": 1.5}}})
        assert len(errors) == 1
        assert "maximum" in errors[0]


class TestInMemoryBackend:
    def test_get_set(self) -> None:
        be = InMemoryBackend()
        be.set("k", "v")
        assert be.get("k") == "v"

    def test_missing_returns_none(self) -> None:
        be = InMemoryBackend()
        assert be.get("missing") is None

    def test_delete(self) -> None:
        be = InMemoryBackend()
        be.set("k", "v")
        be.delete("k")
        assert be.get("k") is None

    def test_ttl_expiry(self) -> None:
        be = InMemoryBackend()
        be.set("k", "v", ttl=0)
        import time
        time.sleep(0.1)
        assert be.get("k") is None

    def test_size(self) -> None:
        be = InMemoryBackend()
        be.set("a", 1)
        be.set("b", 2)
        assert be.size() == 2

    def test_overview(self) -> None:
        be = InMemoryBackend()
        ov = be.overview()
        assert ov["backend"] == "memory"

    def test_abc_cannot_instantiate(self) -> None:
        with pytest.raises(TypeError):
            StorageBackend()  # type: ignore[abstract]
