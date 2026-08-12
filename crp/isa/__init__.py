# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Intent & Speech-Act Positioning (CRP-SPEC-052)."""

from __future__ import annotations

from crp.isa.coref import CoreferenceResolver
from crp.isa.intent import (
    IntentClassifier,
    IntentTag,
    LLMIntentClassifier,
    ManagedIntentClassifier,
    confidence,
)
from crp.isa.position import build_intent_section

__all__ = [
    "IntentTag",
    "IntentClassifier",
    "ManagedIntentClassifier",
    "LLMIntentClassifier",
    "confidence",
    "CoreferenceResolver",
    "build_intent_section",
]
