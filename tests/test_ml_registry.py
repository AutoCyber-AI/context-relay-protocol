# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Tests for the managed ML model registry."""

from __future__ import annotations

import pytest

from crp.ml import MANAGER, ModelManager, managed_call, register_model


@pytest.fixture(autouse=True)
def _reset_manager() -> None:
    """Isolate tests from the global manager state."""
    MANAGER.clear()
    yield
    MANAGER.clear()


def test_manager_loads_and_caches() -> None:
    mgr = ModelManager()
    mgr.register("test", lambda: {"model": "v1"}, budget_ms=10.0)
    assert mgr.load("test") == {"model": "v1"}
    assert mgr.load("test") == {"model": "v1"}


def test_manager_returns_fallback_on_timeout() -> None:
    mgr = ModelManager()
    mgr.register("slow", lambda: __import__("time").sleep(5), load_timeout_ms=50.0, budget_ms=10.0)
    assert mgr.load("slow") is None


def test_managed_call_uses_fallback() -> None:
    register_model("adder", lambda: 5, budget_ms=10.0)
    result = managed_call("adder", lambda m: m + 10, fallback=-1)
    assert result == 15


def test_missing_model_returns_fallback() -> None:
    assert managed_call("not_registered", lambda m: m, fallback="fallback") == "fallback"


def test_manager_reset_unloads_keeps_spec() -> None:
    mgr = ModelManager()
    mgr.register("reset-me", lambda: {"model": "v1"}, budget_ms=10.0)
    assert mgr.load("reset-me") == {"model": "v1"}
    mgr.reset("reset-me")
    assert not mgr.is_available("reset-me")
    assert mgr.is_registered("reset-me")
    assert mgr.load("reset-me") == {"model": "v1"}
