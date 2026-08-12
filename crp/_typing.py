# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Shared type aliases and protocols for CRP (§audit L5)."""

from __future__ import annotations

from typing import Any, TypeAlias
from collections.abc import Callable

# ── Type aliases ──────────────────────────────────────────────────────────
JSON: TypeAlias = dict[str, Any]
FactID: TypeAlias = str
WindowID: TypeAlias = str
SessionID: TypeAlias = str
TokenCount: TypeAlias = int
EmbeddingVector: TypeAlias = list[float]
EmbeddingFn: TypeAlias = Callable[[list[str]], list[EmbeddingVector]]

# ── Dispatch return types (§audit4 CQ-H2) ────────────────────────────────
# The various dispatch strategies intentionally return different types:
#   dispatch()                → tuple[str, QualityReport]
#   dispatch_hierarchical()   → tuple[list[str], QualityReport]
#   dispatch_stream()         → Generator[StreamEvent, None, None]
#   dispatch_stream_augmented → tuple[str, QualityReport]
# A unified DispatchResult would break tuple unpacking at all call sites.
# The common pattern is (output, QualityReport) where output varies by
# strategy.  See CRPOrchestrator method docstrings for specifics.
