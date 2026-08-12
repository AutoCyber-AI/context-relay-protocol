#!/usr/bin/env python3
# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Live proof-of-operation: CRP v6 Agent SDK with an LM Studio local SLM.

This script connects to a local LM Studio server at the OpenAI-compatible
endpoint and runs a tool-using agent entirely on-device. It prints the answer,
the operation chain, and the CRP governance summary so you can verify CRPv6
is truly operational with a real small model.

Run with LM Studio server active on http://localhost:1234 (default) or set
CRP_LMSTUDIO_URL to the LAN IP:port shown in the server logs.
"""

from __future__ import annotations

import json
import os

import crp
from crp.providers.openai import OpenAIAdapter


# ── Local tools ─────────────────────────────────────────────────────────────


def get_weather(city: str) -> str:
    """Return the current weather for a city."""
    return f"The weather in {city} is 22°C and sunny."


def convert_temp(celsius: float) -> str:
    """Convert Celsius to Fahrenheit."""
    return f"{celsius}°C is {celsius * 9 / 5 + 32:.1f}°F."


# ── Connect to LM Studio local SLM ──────────────────────────────────────────


lmstudio_url = os.environ.get("CRP_LMSTUDIO_URL", "http://localhost:1234/v1")
model = os.environ.get("CRP_LMSTUDIO_MODEL", "meta-llama-3.1-8b-instruct")

print(f"Connecting to LM Studio at {lmstudio_url} using model {model}...")

provider = OpenAIAdapter(
    model=model,
    base_url=lmstudio_url,
    api_key="lm-studio",  # local servers ignore this value
)


# ── Declare agent ─────────────────────────────────────────────────────────


agent = crp.Agent(
    provider=provider,
    tools=[get_weather, convert_temp],
    system=(
        "You are a helpful weather assistant. You have tools to get the weather "
        "and convert temperatures. Use them when needed."
    ),
    profile="small-local",  # SLM-first execution profile
)


# ── Run live task ─────────────────────────────────────────────────────────


if __name__ == "__main__":
    questions = [
        "What is the weather in Sydney?",
        "Convert 25°C to Fahrenheit.",
    ]

    for question in questions:
        print(f"\nUser: {question}")
        result = agent.run(question)
        print(f"Agent: {result.answer}")
        print(f"Operations: {result.how_it_was_built}")
        print(f"CRP risk={result.crp.risk} grounded={result.crp.grounded} chain_valid={result.crp.chain_valid}")

    # Carry CSO across turns to prove state relay.
    first = agent.run("What is the weather in London?")
    second = agent.run("What was the temperature I just asked about?", prior_cso=first.cso)
    print("\n--- CSO carry-forward test ---")
    print(f"First:  {first.answer}")
    print(f"Second: {second.answer}")
    print(f"Operations: {second.how_it_was_built}")
