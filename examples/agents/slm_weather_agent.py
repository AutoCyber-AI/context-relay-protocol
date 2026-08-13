#!/usr/bin/env python3
# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""SLM-ready weather agent.

Runs against any OpenAI-compatible endpoint (LM Studio, Ollama, etc.).
Set CRP_LMSTUDIO_URL and CRP_LMSTUDIO_MODEL, or use the defaults.
"""

from __future__ import annotations

import os

import crp
from crp.providers.openai import OpenAIAdapter


def get_weather(city: str) -> str:
    """Return the current weather for a city."""
    return f"The weather in {city} is 22°C and sunny."


def convert_temp(celsius: float) -> str:
    """Convert Celsius to Fahrenheit."""
    return f"{celsius}°C is {celsius * 9 / 5 + 32:.1f}°F."


def main() -> None:
    url = os.environ.get("CRP_LMSTUDIO_URL", "http://localhost:1234/v1")
    model = os.environ.get("CRP_LMSTUDIO_MODEL", "meta-llama-3.1-8b-instruct")

    provider = OpenAIAdapter(model=model, base_url=url, api_key="lm-studio")
    agent = crp.Agent(
        provider=provider,
        tools=[get_weather, convert_temp],
        system="You are a helpful weather assistant.",
        profile="small-local",
    )

    question = "What is the weather in Sydney and convert it to Fahrenheit?"
    result = agent.run(question)

    print(f"Q: {question}")
    print(f"A: {result.answer}")
    print(f"Operations: {result.operations}")
    print(f"Risk: {result.crp.risk} | Grounded: {result.crp.grounded} | Chain valid: {result.crp.chain_valid}")
    print(f"Sources: {len(result.sources)}")


if __name__ == "__main__":
    main()
