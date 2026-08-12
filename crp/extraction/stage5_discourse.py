# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Stage 5 — Discourse structure extraction (SHOULD, ~150ms, CPU-only).

Detects discourse markers and maps them to semantic relation types (RST-inspired).
Trigger: content_type in {REASONING_DENSE, NARRATIVE}.
No ML model — pure pattern matching over sentences.
"""

from __future__ import annotations

import re

from crp.extraction.types import Fact, FactEdge, RelationType

# ---------------------------------------------------------------------------
# Discourse marker → relation-type mapping
# ---------------------------------------------------------------------------

_MARKER_GROUPS: list[tuple[RelationType, list[str]]] = [
    (RelationType.CONDITION_FOR, [
        "if", "unless", "provided", "provided that", "assuming",
        "given that", "in case", "on condition that",
    ]),
    (RelationType.CAUSE_EFFECT, [
        "because", "since", "due to", "owing to", "causes",
        "caused by", "as a result of",
    ]),
    (RelationType.CONTRAST, [
        "however", "but", "yet", "on the other hand",
        "in contrast", "conversely", "nevertheless",
    ]),
    (RelationType.CONCESSION, [
        "although", "despite", "even though", "in spite of",
        "notwithstanding", "regardless",
    ]),
    (RelationType.CONSEQUENCE, [
        "therefore", "thus", "hence", "so", "consequently",
        "as a result", "accordingly",
    ]),
    (RelationType.ELABORATION, [
        "as", "given", "for example", "for instance",
        "in particular", "specifically", "namely",
        "that is", "i.e.", "e.g.",
    ]),
    (RelationType.SEQUENCE, [
        "and then", "subsequently", "next", "afterwards",
        "following", "before", "after", "finally",
        "first", "second", "third", "lastly",
    ]),
]

# Build compiled regex per group — match markers at word boundaries
_COMPILED_MARKERS: list[tuple[RelationType, re.Pattern[str]]] = []
for _rel, _markers in _MARKER_GROUPS:
    # Sort longest first so "provided that" matches before "provided"
    _sorted = sorted(_markers, key=len, reverse=True)
    escaped = [re.escape(m) for m in _sorted]
    _COMPILED_MARKERS.append((
        _rel,
        re.compile(r"\b(?:" + "|".join(escaped) + r")\b", re.IGNORECASE),
    ))

# Flat set for quick counting
_ALL_MARKERS_FLAT: set[str] = set()
for _, markers in _MARKER_GROUPS:
    _ALL_MARKERS_FLAT.update(markers)

# ---------------------------------------------------------------------------
# Sentence splitting (reuse from stage2 would be nice, but keep self-contained)
# ---------------------------------------------------------------------------

_SENT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")


def _split_sentences(text: str) -> list[str]:
    raw = _SENT_RE.split(text.strip())
    return [s.strip() for s in raw if len(s.strip()) > 5]


# ---------------------------------------------------------------------------
# Public helpers (used by complexity detector)
# ---------------------------------------------------------------------------

def count_discourse_markers(text: str) -> int:
    """Count total discourse-marker occurrences in *text* (fast)."""
    total = 0
    text_lower = text.lower()
    for marker in _ALL_MARKERS_FLAT:
        # Word-boundary check via regex on each marker would be expensive;
        # for the counting use-case a simple substring is sufficient.
        start = 0
        while True:
            idx = text_lower.find(marker, start)
            if idx == -1:
                break
            # Rough word-boundary check
            before_ok = idx == 0 or not text_lower[idx - 1].isalnum()
            after_idx = idx + len(marker)
            after_ok = after_idx >= len(text_lower) or not text_lower[after_idx].isalnum()
            if before_ok and after_ok:
                total += 1
            start = idx + 1
    return total


# ---------------------------------------------------------------------------
# Stage 5 Extractor
# ---------------------------------------------------------------------------

class DiscourseExtractor:
    """Stage 5 — discourse-structure extraction (CPU-only)."""

    def extract(
        self,
        text: str,
        source_window_id: str = "",
    ) -> tuple[list[Fact], list[FactEdge]]:
        """Detect discourse markers and create FactEdge relations.

        Returns ``(marker_facts, edges)`` where *marker_facts* are the
        clauses surrounding each detected marker, and *edges* link them.
        """
        sentences = _split_sentences(text)
        if not sentences:
            return [], []

        facts: list[Fact] = []
        edges: list[FactEdge] = []
        sent_fact_ids: dict[int, str] = {}  # sentence_index → fact_id

        def _get_or_create_fact(idx: int) -> str:
            """Ensure a Fact exists for the sentence at *idx*."""
            if idx in sent_fact_ids:
                return sent_fact_ids[idx]
            f = Fact(
                text=sentences[idx],
                category="discourse_unit",
                source_window_id=source_window_id,
                confidence=0.70,
                extraction_stage=5,
                metadata={"sentence_index": idx},
            )
            facts.append(f)
            sent_fact_ids[idx] = f.id
            return f.id

        for i, sent in enumerate(sentences):
            for rel_type, pattern in _COMPILED_MARKERS:
                match = pattern.search(sent)
                if match is None:
                    continue

                # The marker links this sentence (or the clause after the marker)
                # to the preceding sentence.
                before_idx = max(0, i - 1)
                after_idx = i

                # Avoid self-loops
                if before_idx == after_idx and i == 0:
                    continue

                before_id = _get_or_create_fact(before_idx)
                after_id = _get_or_create_fact(after_idx)

                edges.append(FactEdge(
                    source_id=before_id,
                    target_id=after_id,
                    relation_type=rel_type,
                    confidence=0.70,
                    source_stage=5,
                    metadata={"marker": match.group(0), "sentence_index": i},
                ))

        return facts, edges
