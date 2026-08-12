# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Shared test fixtures for CRP test suite."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("CRP_DISABLE_WATERMARK", "1")


@pytest.fixture
def enable_watermark(monkeypatch):
    """Re-enable license watermarking for tests that explicitly assert it."""
    monkeypatch.delenv("CRP_DISABLE_WATERMARK", raising=False)


from crp.core.task_intent import TaskIntent


@pytest.fixture
def sample_task_intent() -> TaskIntent:
    """Minimal TaskIntent for testing."""
    return TaskIntent(
        system_prompt="You are a helpful assistant.",
        task_input="Explain the Context Relay Protocol.",
    )


@pytest.fixture
def sample_system_prompt() -> str:
    return "You are a helpful assistant."


@pytest.fixture
def sample_task_input() -> str:
    return "What is CRP?"
