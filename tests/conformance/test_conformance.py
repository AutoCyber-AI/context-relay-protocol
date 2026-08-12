# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Pytest entry point for the CRP conformance test-vector suite (SPEC-014).

Each JSON vector becomes a parametrised test case so failures are reported
per-vector with the failing assertion detail.
"""

from __future__ import annotations

import pytest

from tests.conformance.levels import ConformanceLevel, mandatory_headers
from tests.conformance.runner import load_vectors, run_vector

_VECTORS = load_vectors()


@pytest.mark.parametrize("vector", _VECTORS, ids=[v["test_id"] for v in _VECTORS])
def test_conformance_vector(vector):
    result = run_vector(vector)
    assert result.passed, f"{result.test_id} failed: {result.failures}"


def test_vectors_loaded():
    assert _VECTORS, "no conformance vectors were discovered"


@pytest.mark.parametrize("level", list(ConformanceLevel))
def test_mandatory_headers_nonempty(level):
    headers = mandatory_headers(level)
    assert headers, f"no mandatory headers for {level}"
    assert all(isinstance(h, str) and h for h in headers)
