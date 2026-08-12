# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""CRP conformance test suite (CRP-SPEC-014).

Public entry points for the JSON test-vector runner. Use :func:`run_all` to
execute every vector or :func:`run_vector` for a single one.
"""

from __future__ import annotations

from .levels import (
    BASIC_MANDATORY_HEADERS,
    STANDARD_MANDATORY_HEADERS,
    ConformanceLevel,
    mandatory_headers,
)
from .runner import (
    AssertionResult,
    VectorResult,
    load_vectors,
    run_all,
    run_vector,
)

__all__ = [
    "ConformanceLevel",
    "BASIC_MANDATORY_HEADERS",
    "STANDARD_MANDATORY_HEADERS",
    "mandatory_headers",
    "AssertionResult",
    "VectorResult",
    "load_vectors",
    "run_all",
    "run_vector",
]
