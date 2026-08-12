# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Stage 6 — LLM-assisted relational extraction (MAY, expensive).

Dispatches a dedicated extraction window to a small LLM to extract logical
relationships from reasoning-dense content. Trigger: content_type == REASONING_DENSE
AND Stage 5 edge_yield < 0.1 edges/sentence.

This stage is **user-configurable** (can be disabled via config flag).
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable

from crp.extraction.types import Fact, FactEdge, RelationType

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Extraction prompt
# ---------------------------------------------------------------------------

_EXTRACTION_PROMPT = (
    "Extract ALL logical relationships, conditions, dependencies, "
    "and reasoning chains from this text. Output as a JSON array of objects "
    'with keys: "subject", "predicate", "object". Example:\n'
    '[{"subject": "A", "predicate": "causes", "object": "B"}]'
)

_RELATION_MAP: dict[str, RelationType] = {
    "causes": RelationType.CAUSE_EFFECT,
    "caused by": RelationType.CAUSE_EFFECT,
    "leads to": RelationType.CONSEQUENCE,
    "results in": RelationType.CONSEQUENCE,
    "depends on": RelationType.CONDITION_FOR,
    "requires": RelationType.CONDITION_FOR,
    "if": RelationType.CONDITION_FOR,
    "contrasts": RelationType.CONTRAST,
    "despite": RelationType.CONCESSION,
    "elaborates": RelationType.ELABORATION,
    "follows": RelationType.SEQUENCE,
}

# ---------------------------------------------------------------------------
# Dispatch callback type
# ---------------------------------------------------------------------------

# Type alias for the LLM dispatch function the pipeline will inject.
# Signature: dispatch(system_prompt, task_input, max_output_tokens) → str
DispatchFn = Callable[[str, str, int], str]


# ---------------------------------------------------------------------------
# Response parser
# ---------------------------------------------------------------------------

_JSON_ARRAY_RE = re.compile(r"\[.*\]", re.DOTALL)


def _parse_extraction_response(raw: str) -> list[dict[str, str]]:
    """Best-effort JSON parse from LLM output."""
    m = _JSON_ARRAY_RE.search(raw)
    if not m:
        logger.debug("Stage 6: no JSON array found in LLM response (%d chars)", len(raw))
        return []
    try:
        data = json.loads(m.group(0))
        if isinstance(data, list):
            return [d for d in data if isinstance(d, dict)]
    except (json.JSONDecodeError, ValueError):
        logger.debug("Stage 6: JSON parse failed for extraction response")
    return []


def _map_predicate(predicate: str) -> RelationType:
    pred = predicate.strip().lower()
    for key, rel in _RELATION_MAP.items():
        if key in pred:
            return rel
    return RelationType.RELATED


# ---------------------------------------------------------------------------
# Stage 6 Extractor
# ---------------------------------------------------------------------------

class LLMExtractor:
    """Stage 6 — LLM-assisted extraction (optional, expensive).

    Requires a *dispatch_fn* to be injected by the pipeline. If not set,
    ``extract()`` returns empty.
    """

    def __init__(self, dispatch_fn: DispatchFn | None = None) -> None:
        self._dispatch = dispatch_fn

    @property
    def is_available(self) -> bool:
        """Return whether this object is available."""
        return self._dispatch is not None

    def set_dispatch(self, fn: DispatchFn) -> None:
        """Inject the dispatch function used to call the LLM.

        Args:
            fn: Callable with signature ``(system_prompt, task_input, max_output_tokens) -> str``.
        """
        self._dispatch = fn

    def extract(
        self,
        text: str,
        source_window_id: str = "",
        max_input_chars: int = 8000,
        max_output_tokens: int = 1024,
    ) -> tuple[list[Fact], list[FactEdge]]:
        """Dispatch extraction window and parse results.

        Returns ``(facts, edges)`` or ``([], [])`` if dispatch unavailable.
        """
        if self._dispatch is None:
            return [], []

        # Chunk if necessary
        chunk = text[:max_input_chars]

        try:
            raw = self._dispatch(_EXTRACTION_PROMPT, chunk, max_output_tokens)
        except Exception:
            logger.exception("Stage 6 LLM dispatch failed")
            return [], []

        triples = _parse_extraction_response(raw)
        if not triples:
            return [], []

        facts: list[Fact] = []
        edges: list[FactEdge] = []
        seen: dict[str, str] = {}

        for triple in triples:
            subj = str(triple.get("subject", "")).strip()
            obj = str(triple.get("object", "")).strip()
            pred = str(triple.get("predicate", "")).strip()
            if not subj or not obj:
                continue

            if subj not in seen:
                sf = Fact(
                    text=subj,
                    category="llm_entity",
                    source_window_id=source_window_id,
                    confidence=0.75,
                    extraction_stage=6,
                    metadata={"role": "subject"},
                )
                facts.append(sf)
                seen[subj] = sf.id
            if obj not in seen:
                of = Fact(
                    text=obj,
                    category="llm_entity",
                    source_window_id=source_window_id,
                    confidence=0.75,
                    extraction_stage=6,
                    metadata={"role": "object"},
                )
                facts.append(of)
                seen[obj] = of.id

            edges.append(FactEdge(
                source_id=seen[subj],
                target_id=seen[obj],
                relation_type=_map_predicate(pred),
                confidence=0.75,
                source_stage=6,
                metadata={"predicate": pred},
            ))

        return facts, edges
