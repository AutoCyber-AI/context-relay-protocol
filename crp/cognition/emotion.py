# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Lightweight emotion/affect detection for cognitive presets (CRP-SPEC-046 §2.2).

The default detector is rule-based and runs locally with no model dependencies.
When ``transformers`` is available, a preset can opt into an ML recognizer via
``emotions.recognizer: ml``; if the model is missing or slow, the rule-based
fallback is used automatically.
"""

from __future__ import annotations

import re
from typing import Any

# Simple keyword maps for rule-based affect detection.
_AFFECT_KEYWORDS: dict[str, list[str]] = {
    "frustrated": ["frustrated", "annoyed", "angry", "mad", "furious", "stupid", "useless"],
    "anxious": ["worried", "anxious", "scared", "nervous", "stressed", "urgent", "emergency"],
    "sad": ["sad", "upset", "disappointed", "depressed", "unhappy"],
    "happy": ["happy", "excited", "glad", "pleased", "thank", "thanks", "awesome"],
    "confused": ["confused", "lost", "don't understand", "unclear", "what do you mean"],
    "curious": ["curious", "wonder", "how does", "why does", "explain"],
    "compassion": ["compassion", "kind", "gentle", "care", "hurt", "suffering", "sad"],
}


def detect_emotion(text: str, *, top_n: int = 2) -> dict[str, Any]:
    """Return rule-based affect labels and scores for ``text``.

    Args:
        text: User message or tool output to classify.
        top_n: Number of top affect labels to return.

    Returns:
        Dict with ``primary``, ``scores`` (dict label→score), and ``method``.
    """
    text_lower = text.lower()
    scores: dict[str, float] = {}
    for affect, keywords in _AFFECT_KEYWORDS.items():
        score = sum(1.0 for kw in keywords if re.search(r"\b" + re.escape(kw) + r"\b", text_lower))
        if score > 0:
            scores[affect] = score

    if not scores:
        scores["neutral"] = 1.0

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    primary = ranked[0][0]
    return {
        "primary": primary,
        "scores": dict(ranked[:top_n]),
        "method": "rule",
    }


def detect_emotion_ml(text: str, *, model_id: str = "j-hartmann/emotion-english-distilroberta-base") -> dict[str, Any]:
    """Optional ML-based emotion recognition with graceful fallback.

    This is intentionally not a hard dependency.  If ``transformers`` is not
    installed or the model cannot load, the rule-based detector is used.
    """
    try:
        from transformers import pipeline  # type: ignore[import-untyped]

        classifier = pipeline("text-classification", model=model_id, top_k=None)
        results = classifier(text)
        if results and isinstance(results[0], list):
            results = results[0]
        scores = {r["label"].lower(): r["score"] for r in results}
        primary = max(scores, key=lambda label: scores[label]) if scores else "neutral"
        return {"primary": primary, "scores": scores, "method": "ml"}
    except Exception:
        return detect_emotion(text)
