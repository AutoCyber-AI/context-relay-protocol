#!/usr/bin/env python3
# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""CRP v6 Agent SDK — minimal reference agent.

This example shows how to declare an agent with typed tools and run the
positioned loop.  It uses a mock provider so it works without an API key or
local model, but the same code runs against OpenAI, Ollama, LM Studio, or the
CRP Gateway by swapping the provider.
"""

from __future__ import annotations

import json

import crp
from crp.providers.custom import CustomProvider

# ── Tools ─────────────────────────────────────────────────────────────────

def get_weather(city: str) -> str:
    """Return the current weather for a city."""
    return f"The weather in {city} is 22°C and sunny."


def convert_temp(celsius: float) -> str:
    """Convert Celsius to Fahrenheit."""
    return f"{celsius}°C is {celsius * 9 / 5 + 32:.1f}°F."


# ── Mock SLM provider ──────────────────────────────────────────────────────
#
# In production, replace this with crp.SDKClient(provider=my_real_provider).
# The mock reads the tool-positioning frame from the prompt and emits the
# structured JSON call CRP expects.

def _mock_generate(messages: list[dict[str, str]]) -> tuple[str, str]:
    prompt = messages[-1]["content"]
    lower = prompt.lower()

    # The user's actual request lives on the "objective:" line; ignore tool
    # description noise elsewhere in the positioning frame.
    import re
    objective_match = re.search(r"objective:\s*(.+)", lower)
    objective = objective_match.group(1).strip() if objective_match else lower

    is_weather_request = (
        "weather" in objective
        or "sydney" in objective
        or "london" in objective
    )
    is_convert_request = (
        "fahrenheit" in objective
        or ("convert" in objective and not is_weather_request)
    )

    if is_convert_request:
        m = re.search(r"(\d+(?:\.\d+)?)\s*°?c", objective)
        celsius = float(m.group(1)) if m else 22.0
        return (
            json.dumps({"capability_id": "convert_temp", "arguments": {"celsius": celsius}}),
            "stop",
        )
    if is_weather_request:
        city = "Sydney" if "sydney" in objective else "London"
        return (
            json.dumps({"capability_id": "get_weather", "arguments": {"city": city}}),
            "stop",
        )
    return (
        json.dumps({"capability_id": None, "answer": "I can check the weather or convert temperature."}),
        "stop",
    )


provider = CustomProvider(
    generate_fn=_mock_generate,
    count_tokens_fn=lambda text: max(1, len(text.split())),
    context_size=8192,
    name="mock-slm",
)


# ── Agent declaration ─────────────────────────────────────────────────────

agent = crp.Agent(
    provider=provider,
    tools=[get_weather, convert_temp],
    system="You are a helpful weather assistant.",
    profile="frontier",
)


# ── Run ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    result = agent.run("What is the weather in Sydney?")
    print(result.answer)
    print("Operations:", result.how_it_was_built)
    print("Tool observations:", len(result.sources))

    result2 = agent.run("Convert 22°C to Fahrenheit", prior_cso=result.cso)
    print(result2.answer)
