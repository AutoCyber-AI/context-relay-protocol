#!/usr/bin/env python3
# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Flagship template — user-defined reasoning: Socratic tutor.

This template shows how a user-defined reasoning scaffold turns any agent into a
Socratic tutor without rewriting the agent loop. The preset defines the
thinking process; CRP runs it.

Run:
    python examples/templates/socratic_tutor_agent.py "Why is the sky blue?"
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import crp
from _shared import resolve_provider


def main() -> None:
    topic = " ".join(sys.argv[1:]) or "Why is the sky blue?"
    provider = resolve_provider()

    agent = crp.Agent(
        provider=provider,
        preset="socratic_tutor",
        profile="small-local",
        depth="standard",
    )

    print("=" * 70)
    print("SOCRATIC TUTOR — preset:", agent._preset.name if agent._preset else "none")
    print("=" * 70)
    print(f"Question: {topic!r}\n")

    result = agent.run(topic)
    print(f"Response:\n{result.answer}\n")
    print(f"Operations: {result.how_it_was_built}")
    print(f"Risk: {result.crp.risk} | Grounded: {result.crp.grounded} | Chain valid: {result.crp.chain_valid}")


if __name__ == "__main__":
    main()
