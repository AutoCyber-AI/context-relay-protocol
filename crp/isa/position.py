# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Build the interpreted-intent envelope section (CRP-SPEC-052 §4.3.3)."""

from __future__ import annotations

from crp.isa.intent import IntentTag, confidence


def build_intent_section(raw_turn: str, intent_tag: IntentTag, resolved_turn: str) -> dict:
    """Assemble the ``interpreted_intent`` envelope section (SPEC-003).

    Args:
        raw_turn: Original user text.
        intent_tag: Pragmatic classification from the intent classifier.
        resolved_turn: User text after coreference resolution.

    Returns:
        Dictionary ready to be attached to the context envelope.
    """
    return {
        "raw": raw_turn,
        "resolved": resolved_turn,
        "speech_act": intent_tag.speech_act,
        "directness": round(intent_tag.directness, 3),
        "constraints": list(intent_tag.implied_constraints),
        "tone_hint": "acknowledge_friction" if intent_tag.valence < 0 else "neutral",
        "intent_confidence": confidence(intent_tag),
    }
