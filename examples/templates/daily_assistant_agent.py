#!/usr/bin/env python3
# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Flagship template — Personal Study & Daily Assistant.

The most universally relatable agent shape: something a student, a member of
staff, or anyone who just wants a helpful daily companion could actually use.
Checks the weather, converts units, remembers what you tell it across the
whole conversation, and quizzes you for fun. Runs against a REAL model
(LM Studio / OpenAI / Anthropic / Ollama — auto-detected).

Protocol features this template exercises:

  - Tool Capability Fabric   — four small, real tools positioned per turn
  - CSO / memory relay       — the star of this template: `remember_note` /
                                `recall_notes` are backed by real Python state,
                                but the AGENT's own memory of "what have we
                                talked about" comes entirely from carrying the
                                CSO forward turn-to-turn (`prior_cso=`) — by
                                the last turn it can recall facts from three
                                turns back without re-stating them
  - profile="small-local"    — tuned for a genuinely small model, not a
                                frontier one; this is the "runs on your laptop,
                                no cloud, no cost" use case
  - Quality tiers             — printed every turn so you can see the model's
                                self-reported confidence change turn to turn

Honest note: this is the hardest of the three flagship templates for a small
(7-8B) local model — precisely because it asks for accurate fact
*discrimination* across five turns of accumulated state, not just retrieval.
Expect occasional imprecise recall (e.g. blending the weather fact into the
"what did I ask you to remember" answer) with a genuinely small model; it
will never crash or show broken/raw output, and grounding/quality reporting
stays honest throughout — the model's capability ceiling is visible, not
hidden. Larger local models (14B+) resolve this reliably in practice.

Run:
    python examples/templates/daily_assistant_agent.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import crp
from _shared import resolve_provider

# ── Tools ────────────────────────────────────────────────────────────────

_WEATHER = {
    "sydney": {"temp_c": 22, "condition": "sunny"},
    "london": {"temp_c": 14, "condition": "cloudy"},
    "tokyo": {"temp_c": 27, "condition": "humid"},
}

_notes: list[str] = []


def get_weather(city: str) -> dict:
    """Get the current weather for a city."""
    return _WEATHER.get(city.lower(), {"temp_c": 18, "condition": "unknown"})


def convert_units(value: float, from_unit: str, to_unit: str) -> str:
    """Convert a value between common units (celsius/fahrenheit, km/miles, kg/lb)."""
    table = {
        ("celsius", "fahrenheit"): lambda v: v * 9 / 5 + 32,
        ("fahrenheit", "celsius"): lambda v: (v - 32) * 5 / 9,
        ("km", "miles"): lambda v: v * 0.621371,
        ("miles", "km"): lambda v: v / 0.621371,
        ("kg", "lb"): lambda v: v * 2.20462,
        ("lb", "kg"): lambda v: v / 2.20462,
    }
    fn = table.get((from_unit.lower(), to_unit.lower()))
    if fn is None:
        return f"Don't know how to convert {from_unit} to {to_unit}."
    return f"{value} {from_unit} = {fn(value):.2f} {to_unit}"


def remember_note(note: str) -> dict:
    """Remember something the user said, so it can be recalled later this session."""
    _notes.append(note)
    return {"status": "saved", "note": note, "total_notes": len(_notes)}


def recall_notes() -> list[str]:
    """Recall everything the user has asked to remember this session."""
    return list(_notes) or ["(nothing saved yet)"]


def quiz_me(topic: str) -> dict:
    """Generate a one-question fun trivia/study quiz on a topic."""
    bank = {
        "chemistry": {"q": "What is the chemical symbol for gold?", "a": "Au"},
        "geography": {"q": "What is the smallest country in the world?", "a": "Vatican City"},
        "space": {"q": "Which planet has the most moons?", "a": "Saturn"},
    }
    return bank.get(topic.lower(), {"q": f"(no question bank yet for {topic})", "a": ""})


def _badge(result: crp.AgentResponse) -> str:
    risk_icon = {"LOW": "🟢", "MEDIUM": "🟡", "HIGH": "🟠", "CRITICAL": "🔴"}.get(result.crp.risk, "⚪")
    return f"{risk_icon} {result.crp.risk}  |  grounded={result.crp.grounded}"


def main() -> None:
    provider = resolve_provider()

    agent = crp.Agent(
        provider=provider,
        tools=[get_weather, convert_units, remember_note, recall_notes, quiz_me],
        system="You are a friendly personal daily assistant for a student.",
        profile="small-local",
    )

    turns = [
        "What's the weather in Sydney right now?",
        "Convert that temperature to Fahrenheit.",
        "Remember that I have a chemistry exam this Friday.",
        "Quiz me on chemistry to help me study.",
        "What have I asked you to remember so far this conversation?",
    ]

    cso = None
    for i, turn in enumerate(turns, start=1):
        print("=" * 70)
        print(f"TURN {i} — {turn}")
        print("=" * 70)
        result = agent.run(turn, prior_cso=cso)
        cso = result.cso
        print(f"A: {result.answer}\n")
        print(f"Operations: {result.how_it_was_built}  |  {_badge(result)}")
        print(f"Facts in memory so far: {len(cso.established_facts)}\n")


if __name__ == "__main__":
    main()
