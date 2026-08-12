# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""6-stage graduated extraction pipeline — regex → statistical → NER → UIE → discourse → LLM."""

from crp.extraction.complexity import detect_content_complexity
from crp.extraction.contradiction import apply_supersessions, detect_contradictions
from crp.extraction.pipeline import ExtractionPipeline
from crp.extraction.quality_gate import run_quality_gate
from crp.extraction.structured_output import StructuredOutputHandler
from crp.extraction.types import (
    ContentType,
    Contradiction,
    ExtractionResult,
    Fact,
    FactEdge,
    FactEvent,
    FactGraph,
    RelationType,
    ValidationIssue,
    ValidationResult,
    ValidationSeverity,
)

__all__ = [
    # Data types
    "ContentType",
    "Contradiction",
    "ExtractionResult",
    "Fact",
    "FactEdge",
    "FactEvent",
    "FactGraph",
    "RelationType",
    "ValidationIssue",
    "ValidationResult",
    "ValidationSeverity",
    # Pipeline
    "ExtractionPipeline",
    # Helpers
    "detect_content_complexity",
    "detect_contradictions",
    "apply_supersessions",
    "run_quality_gate",
    "StructuredOutputHandler",
]
