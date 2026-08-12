# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Cross-session coreference resolution (CRP-SPEC-052 §4.3.2).

Resolves pronouns/deixis ("it", "that approach", "the second option") against a
session entity registry before the envelope is packed.  The default
implementation is rule-based and dependency-free; if ``fastcoref`` is installed,
it is loaded lazily through :mod:`crp.ml` and constrained to a millisecond
budget, falling back to the rule-based resolver if the model is slow or absent.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any

from crp.ml import MANAGER

logger = logging.getLogger(__name__)

_PRONOUNS = {
    "it", "that", "this", "they", "them", "he", "she",
    "those", "these", "him", "her", "its",
}

_ORDINALS = {
    "first": 0,
    "second": 1,
    "third": 2,
    "fourth": 3,
    "fifth": 4,
    "sixth": 5,
}


def _is_pronoun(mention: str) -> bool:
    return mention.strip().lower() in _PRONOUNS


def _normalize_mention(mention: str) -> str:
    return re.sub(r"[^\w\s]", "", mention).strip().lower()


def _fastcoref_loader() -> Any:
    """Lazily import and instantiate fastcoref."""
    from fastcoref import FCoref  # type: ignore[import-untyped]

    model_name = os.getenv("CRP_COREF_MODEL", "")
    kwargs: dict[str, Any] = {}
    if model_name:
        kwargs["model_name_or_path"] = model_name
    return FCoref(**kwargs)


# Register the optional neural coref model.  No import happens until load().
MANAGER.register(
    "crp.isa.fastcoref",
    _fastcoref_loader,
    budget_ms=50.0,
    load_timeout_ms=30000.0,
)


class CoreferenceResolver:
    """Resolve pronouns and deixis against a session entity registry."""

    def __init__(self, budget_ms: float = 20.0) -> None:
        self._budget_ms = budget_ms
        self._model_failed: bool = False

    def resolve(self, turn: str, session_entities: dict[str, str]) -> str:
        """Rewrite ambiguous references in ``turn`` using ``session_entities``.

        Args:
            turn: The raw user turn.
            session_entities: Mapping of entity id -> canonical mention text.

        Returns:
            The resolved turn. Pronouns are replaced when a canonical antecedent
            can be found; ordinal deixis ("the second option") is resolved from
            the registry order.
        """
        rewritten = turn
        if session_entities:
            rewritten = self._resolve_with_model(turn, session_entities)
            rewritten = self._resolve_ordinals(rewritten, list(session_entities.values()))
        return rewritten

    def _resolve_with_model(self, turn: str, session_entities: dict[str, str]) -> str:
        """Try neural coref under budget, fall back to simple pronoun replacement."""
        recent = list(session_entities.values())[-6:]
        text = " ".join(recent + [turn])
        try:
            if not self._model_failed:

                def _predict(model: Any) -> Any:
                    return model.predict(texts=[text])

                preds = MANAGER.run(
                    "crp.isa.fastcoref",
                    _predict,
                    budget_ms=self._budget_ms,
                    fallback=None,
                )
                if preds is not None:
                    clusters = preds[0].get_clusters()
                    rewritten = turn
                    for cluster in clusters:
                        canonical = self._canonical_from_cluster(cluster)
                        if not canonical:
                            continue
                        for mention in cluster:
                            if _is_pronoun(mention):
                                rewritten = self._replace_first_word(rewritten, mention, canonical)
                    return rewritten
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("Neural coref failed: %s", exc)
            self._model_failed = True
        return self._fallback_pronoun_replace(turn, recent)

    def _canonical_from_cluster(self, cluster: list[str]) -> str | None:
        non_pronouns = [m for m in cluster if not _is_pronoun(m)]
        if not non_pronouns:
            return None
        return max(non_pronouns, key=len)

    def _replace_first_word(self, text: str, old: str, new: str) -> str:
        """Replace the first whole-word occurrence of ``old`` with ``new``."""
        pattern = re.compile(r"\b" + re.escape(old) + r"\b", re.IGNORECASE)
        return pattern.sub(new, text, count=1)

    def _fallback_pronoun_replace(self, turn: str, recent: list[str]) -> str:
        """If no neural model, replace "it"/"that"/"this" with the most recent entity."""
        if not recent:
            return turn
        latest = recent[-1]
        rewritten = turn
        for pronoun in ("it", "that", "this"):
            pattern = re.compile(r"\b" + pronoun + r"\b", re.IGNORECASE)
            if pattern.search(rewritten):
                rewritten = pattern.sub(latest, rewritten, count=1)
                break
        return rewritten

    def _resolve_ordinals(self, turn: str, entity_values: list[str]) -> str:
        """Resolve phrases like "the second option" to a registry value."""
        if not entity_values:
            return turn

        def repl(match: re.Match[str]) -> str:
            ordinal_word = match.group(1).lower()
            idx = _ORDINALS.get(ordinal_word)
            if ordinal_word in {"last", "previous"}:
                idx = -1
            if idx is None:
                return match.group(0)
            if ordinal_word == "last" and len(entity_values) >= 1:
                return entity_values[-1]
            if 0 <= idx < len(entity_values):
                return entity_values[idx]
            return match.group(0)

        pattern = re.compile(
            r"\bthe\s+(first|second|third|fourth|fifth|sixth|last|previous)\s+"
            r"(option|one|choice|approach|item|thing|plan)\b",
            re.IGNORECASE,
        )
        return pattern.sub(repl, turn)
