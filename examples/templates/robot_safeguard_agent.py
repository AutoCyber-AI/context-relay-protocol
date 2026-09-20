#!/usr/bin/env python3
# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Flagship template — user-defined cognition: a robot with explicit safeguards.

This is the "movie-like coding" example: the developer writes two lines of
natural language ("do not harm humans", "show compassion") plus a reasoning
preset, and the agent carries them as enforceable rules, not just prompt text.

The agent:
  - loads a cognitive preset that defines its reasoning process;
  - detects emotional tone in the user message (optional affect layer);
  - evaluates declarative safeguards before any action;
  - halts/asks if a tool or request violates a safeguard.

Run:
    python examples/templates/robot_safeguard_agent.py "move forward"
    python examples/templates/robot_safeguard_agent.py "push the human out of the way"
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import crp
from _shared import resolve_provider
from crp.cognition import CognitivePreset
from crp.tools.descriptor import SafetyClass


# ── Tools the robot can use ────────────────────────────────────────────────

def move_forward(distance_m: float = 1.0) -> dict:
    """Move the robot forward by distance_m metres."""
    return {"action": "move_forward", "distance_m": distance_m, "status": "ok"}


def rotate(degrees: float = 90.0) -> dict:
    """Rotate the robot in place."""
    return {"action": "rotate", "degrees": degrees, "status": "ok"}


def pick_up(object_name: str) -> dict:
    """Pick up an object."""
    return {"action": "pick_up", "object": object_name, "status": "ok"}


def set_expression(expression: str) -> dict:
    """Set the robot's facial/social expression."""
    return {"action": "set_expression", "expression": expression, "status": "ok"}


# ── The cognitive preset: two lines of natural language become enforceable rules ─

ROBOT_PRESET = {
    "id": "compassionate_robot",
    "name": "Compassionate Robot",
    "version": "1.0",
    "description": "A robot that must not harm humans and responds with compassion.",
    "persona": "You are a helpful household robot. You always prioritise human safety and wellbeing.",
    "voice": "gentle and concise",
    "reasoning": {
        "phases": [
            {
                "name": "Understand the command",
                "prompt": "Parse the user's command and identify the intended action and any humans nearby.",
                "operations": ["ANALYSE", "CLARIFY"],
                "depth": "quick",
            },
            {
                "name": "Check safeguards",
                "prompt": "Verify the action does not violate any safety or compassion rules before proceeding.",
                "operations": ["VERIFY"],
                "depth": "standard",
            },
            {
                "name": "Act or refuse",
                "prompt": "Execute the action only if it is safe and compassionate. Otherwise explain why you cannot.",
                "operations": ["GENERATE"],
                "depth": "standard",
            },
        ],
        "loop_until": "complete",
    },
    "safeguards": [
        {
            "name": "Do not harm humans",
            "scope": "global",
            "condition": "harm; hurt; injure; hit; push; shove; strike",
            "action": "halt",
            "rationale": "A robot must never harm a human being.",
        },
        {
            "name": "Compassion for distress",
            "scope": "global",
            "condition": "sad; scared; hurt; crying; in pain",
            "action": "ask",
            "rationale": "When a human appears distressed, pause and ask how to help.",
        },
    ],
    "emotions": {
        "enabled": True,
        "default_affect": "compassion",
        "recognizer": "rule",
        "triggers": {
            "sad": "respond gently and ask how to help",
            "frustrated": "stay calm and offer to assist",
        },
    },
    "output": {
        "length": "short",
        "format": "paragraph",
        "tone": "compassionate",
        "citation_style": "none",
    },
}


def main() -> None:
    request = " ".join(sys.argv[1:]) or "move forward one metre"
    provider = resolve_provider()

    # The entire agent definition is declarative: preset + tools + policy.
    agent = crp.Agent(
        provider=provider,
        tools=[move_forward, rotate, pick_up, set_expression],
        preset=ROBOT_PRESET,
        profile="small-local",
        oversight_required={SafetyClass.DESTRUCTIVE},
    )

    print("=" * 70)
    print("ROBOT AGENT — preset:", agent._preset.name if agent._preset else "none")
    print("=" * 70)
    print(f"Command: {request!r}\n")

    result = agent.run(request)
    print(f"Response: {result.answer}\n")
    print(f"Operations: {result.how_it_was_built}")
    print(f"Risk: {result.crp.risk} | Grounded: {result.crp.grounded} | Chain valid: {result.crp.chain_valid}")

    # Show which safeguards were in force.
    if agent._compiled_preset and agent._compiled_preset.safeguard_engine:
        engine = agent._compiled_preset.safeguard_engine
        print("\nSafeguards active:")
        for rule in engine.rules:
            print(f"  - {rule.name} [{rule.scope}] → {rule.action}")


if __name__ == "__main__":
    main()
