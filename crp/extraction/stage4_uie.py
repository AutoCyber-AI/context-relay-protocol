# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Stage 4 — UIE relational extraction (SHOULD, ~100ms, lazy model load).

Extracts (subject, predicate, object) triples and converts them to FactEdge
records. Trigger: Stage 3 relation yield < 0.1 per sentence.
Model: UIE / universal IE (~400MB), loaded lazily.
Graceful fallback: returns empty if unavailable.
"""

from __future__ import annotations

import logging
from typing import Any, Protocol, runtime_checkable

from crp.extraction.types import Fact, FactEdge, RelationType

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# UIE model protocol
# ---------------------------------------------------------------------------

@runtime_checkable
class UIEModel(Protocol):
    """Minimal interface for a Universal Information Extraction model."""

    def extract_triples(
        self, text: str
    ) -> list[dict[str, Any]]:
        """Return list of dicts with keys: subject, predicate, object, confidence."""
        ...


# ---------------------------------------------------------------------------
# Triple → FactEdge mapping
# ---------------------------------------------------------------------------

_PREDICATE_TO_RELATION: dict[str, RelationType] = {
    "causes": RelationType.CAUSE_EFFECT,
    "caused by": RelationType.CAUSE_EFFECT,
    "leads to": RelationType.CONSEQUENCE,
    "results in": RelationType.CONSEQUENCE,
    "depends on": RelationType.CONDITION_FOR,
    "requires": RelationType.CONDITION_FOR,
    "contrasts with": RelationType.CONTRAST,
    "despite": RelationType.CONCESSION,
    "elaborates": RelationType.ELABORATION,
    "extends": RelationType.ELABORATION,
    "follows": RelationType.SEQUENCE,
    "precedes": RelationType.SEQUENCE,
}


def _map_predicate(predicate: str) -> RelationType:
    """Best-effort mapping from free-text predicate to RelationType."""
    pred_lower = predicate.strip().lower()
    for key, rel in _PREDICATE_TO_RELATION.items():
        if key in pred_lower:
            return rel
    return RelationType.RELATED


# ---------------------------------------------------------------------------
# Stage 4 Extractor
# ---------------------------------------------------------------------------

class UIEExtractor:
    """Stage 4 — UIE triple extraction (lazy, optional).

    Loads the model on first use. Returns ``(facts, edges)`` where *facts*
    are the subject/object entities and *edges* are the relations.
    If the UIE library is unavailable, all calls return ``([], [])``.
    """

    def __init__(self) -> None:
        self._model: UIEModel | None = None
        self._available: bool | None = None

    # -- Lifecycle ----------------------------------------------------------

    def _ensure_model(self) -> UIEModel | None:
        if self._available is False:
            return None
        if self._model is not None:
            return self._model
        try:
            # Try to import a UIE implementation.
            # The spec is model-agnostic; accept any class exposing extract_triples().
            from uie import UIE  # type: ignore[import-untyped]

            self._model = UIE()  # type: ignore[assignment]
            self._available = True
            logger.info("UIE model loaded successfully")
            return self._model
        except Exception:
            self._available = False
            logger.warning("UIE not available — Stage 4 will be skipped")
            return None

    def unload(self) -> None:
        """Release the loaded UIE model from memory."""
        self._model = None

    @property
    def is_available(self) -> bool:
        """Return whether this object is available."""
        if self._available is None:
            self._ensure_model()
        return self._available is True

    # -- Extraction ---------------------------------------------------------

    def extract(
        self,
        text: str,
        source_window_id: str = "",
    ) -> tuple[list[Fact], list[FactEdge]]:
        """Extract relational triples from *text*.

        Returns ``(facts, edges)`` — each triple yields two Fact items
        (subject, object) and one FactEdge.
        Returns ``([], [])`` on failure or if model unavailable.
        """
        model = self._ensure_model()
        if model is None:
            return [], []

        try:
            triples = model.extract_triples(text)
        except Exception:
            logger.exception("UIE extraction failed")
            return [], []

        facts: list[Fact] = []
        edges: list[FactEdge] = []
        seen_texts: dict[str, str] = {}  # text → fact_id (dedup entities)

        for triple in triples:
            subj_text = str(triple.get("subject", ""))
            obj_text = str(triple.get("object", ""))
            predicate = str(triple.get("predicate", ""))
            conf = float(triple.get("confidence", 0.70))

            if not subj_text or not obj_text:
                continue

            # Dedup entity facts
            if subj_text not in seen_texts:
                subj_fact = Fact(
                    text=subj_text,
                    category="uie_entity",
                    source_window_id=source_window_id,
                    confidence=min(0.85, max(0.70, conf)),
                    extraction_stage=4,
                    metadata={"role": "subject"},
                )
                facts.append(subj_fact)
                seen_texts[subj_text] = subj_fact.id
            subj_id = seen_texts[subj_text]

            if obj_text not in seen_texts:
                obj_fact = Fact(
                    text=obj_text,
                    category="uie_entity",
                    source_window_id=source_window_id,
                    confidence=min(0.85, max(0.70, conf)),
                    extraction_stage=4,
                    metadata={"role": "object"},
                )
                facts.append(obj_fact)
                seen_texts[obj_text] = obj_fact.id
            obj_id = seen_texts[obj_text]

            edges.append(FactEdge(
                source_id=subj_id,
                target_id=obj_id,
                relation_type=_map_predicate(predicate),
                confidence=min(0.85, max(0.70, conf)),
                source_stage=4,
                metadata={"predicate": predicate},
            ))

        return facts, edges
