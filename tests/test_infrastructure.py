# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
"""Tests for infrastructure wiring from config."""

from __future__ import annotations

from crp.config import CRPConfig
from crp.infrastructure import apply_config


def test_default_memory_infrastructure() -> None:
    wired = apply_config(CRPConfig())
    assert wired["audit_sink"] is not None
    assert wired["storage_backend"] is not None
    assert wired["database_url"] == ""


def test_file_audit_sink() -> None:
    config = CRPConfig()
    config.set("infrastructure.audit_sink", "file")
    config.set("infrastructure.audit_path", ":memory:")
    wired = apply_config(config)
    assert wired["audit_sink"] is not None


def test_model_manager_knobs_applied() -> None:
    config = CRPConfig()
    config.set("infrastructure.model_device", "cpu")
    config.set("infrastructure.model_cache_dir", "/tmp/crp_cache")
    wired = apply_config(config)
    mgr = wired["model_manager"]
    assert mgr._default_device == "cpu"
    assert mgr._default_cache_dir == "/tmp/crp_cache"
