# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Content complexity detection — classifies text as ENTITY_RICH, REASONING_DENSE, or NARRATIVE.

Applied to every window output to determine pipeline routing.
"""

from __future__ import annotations

import re

from crp.extraction.stage5_discourse import count_discourse_markers
from crp.extraction.types import ContentType

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SENT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")
_WORD_RE = re.compile(r"\w+", re.UNICODE)
_SUBORD_RE = re.compile(
    r"\b(?:that|which|who|whom|whose|where|when|while|"
    r"whereas|although|because|since|if|unless|until|after|before)\b",
    re.IGNORECASE,
)


def _count_sentences(text: str) -> int:
    """Rough sentence count."""
    return max(len(_SENT_RE.split(text.strip())), 1)


def _count_words(text: str) -> int:
    return len(_WORD_RE.findall(text))


def _count_subordinate_clauses(text: str) -> int:
    return len(_SUBORD_RE.findall(text))


# ---------------------------------------------------------------------------
# Stage 1 entity density (inline — avoids circular import)
# ---------------------------------------------------------------------------

_ENTITY_PATTERNS = [
    re.compile(r"\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b"),
    re.compile(r"\bCVE-\d{4}-\d{4,7}\b"),
    re.compile(r"https?://[^\s\"'<>\])}]+", re.ASCII),
    re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"),
    re.compile(r"\b(?:ERR|ERROR|WARN|FATAL|CRITICAL|E|W)[-_]?\d{3,6}\b", re.IGNORECASE),
    re.compile(r"\bv?\d+\.\d+\.\d+(?:[-+][A-Za-z0-9.]+)?\b"),
]


def _quick_entity_count(text: str) -> int:
    """Fast regex pass for structured entities (subset of Stage 1)."""
    total = 0
    for pat in _ENTITY_PATTERNS:
        total += len(pat.findall(text))
    return total


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def detect_content_complexity(text: str) -> ContentType:
    """Classify text complexity for pipeline routing.

    Thresholds per spec:
      ENTITY_RICH:     entity_density > 0.05
      REASONING_DENSE: discourse_ratio > 0.30 OR subordinate_clause_ratio > 0.40
      NARRATIVE:       everything else
    """
    word_count = _count_words(text)
    sent_count = _count_sentences(text)

    # Entity density
    entity_count = _quick_entity_count(text)
    entity_density = entity_count / max(word_count, 1)

    if entity_density > 0.05:
        return ContentType.ENTITY_RICH

    # Discourse marker ratio
    discourse_count = count_discourse_markers(text)
    discourse_ratio = discourse_count / max(sent_count, 1)

    # Subordinate clause ratio
    subord_count = _count_subordinate_clauses(text)
    subord_ratio = subord_count / max(sent_count, 1)

    if discourse_ratio > 0.30 or subord_ratio > 0.40:
        return ContentType.REASONING_DENSE

    return ContentType.NARRATIVE
