#!/usr/bin/env python3
# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Live side-by-side demo: raw LLM vs CRPv6 Agent SDK.

Connects to a local LM Studio server (or any OpenAI-compatible endpoint) and
runs the same small task twice:

1. Raw LLM call: system prompt lists the tools, model must decide what to do.
2. CRPv6 Agent: declares tools and lets CRP build the positioned frame, execute
   the loop, and report governance metadata.

Both use the same model, the same tools, and the same user question. The
output is designed for a video/screenshot: a clear before/after contrast.

Set CRP_LMSTUDIO_URL and CRP_LMSTUDIO_MODEL, or edit defaults below.
"""

from __future__ import annotations

import json
import os
import textwrap
from typing import Any

import crp
from crp.providers.openai import OpenAIAdapter


# ── Tools (shared by both arms) ─────────────────────────────────────────────


def get_weather(city: str) -> str:
    """Return the current weather for a city."""
    return f"The weather in {city} is 22°C and sunny."


def convert_temp(celsius: float) -> str:
    """Convert Celsius to Fahrenheit."""
    return f"{celsius}°C is {celsius * 9 / 5 + 32:.1f}°F."


# ── LM Studio connection ────────────────────────────────────────────────────


lmstudio_url = os.environ.get("CRP_LMSTUDIO_URL", "http://localhost:1234/v1")
model = os.environ.get("CRP_LMSTUDIO_MODEL", "meta-llama-3.1-8b-instruct")

print(f"Model endpoint: {lmstudio_url}")
print(f"Model:          {model}\n")


# ── Arm 1: raw LLM (no CRP) ─────────────────────────────────────────────────


def run_raw_llm(question: str) -> dict[str, Any]:
    """Ask the same LLM directly, with tool descriptions crammed in the prompt."""
    provider = OpenAIAdapter(
        model=model,
        base_url=lmstudio_url,
        api_key="lm-studio",
    )

    system = textwrap.dedent("""\
        You are a helpful assistant. You have these tools:

        get_weather(city: str) -> returns weather in the city.
        convert_temp(celsius: float) -> converts Celsius to Fahrenheit.

        If you need a tool, output JSON like:
        {"tool": "get_weather", "arguments": {"city": "Sydney"}}
        Then stop. The user will give you the result.

        Answer the user's question.""")

    output, _reason = provider.generate_chat([
        {"role": "system", "content": system},
        {"role": "user", "content": question},
    ])

    return {
        "mode": "RAW LLM",
        "response": output,
        "tool_used": None,
        "governance": None,
    }


# ── Arm 2: CRPv6 Agent SDK ──────────────────────────────────────────────────


def run_crp_agent(question: str) -> dict[str, Any]:
    """Run the same task through the CRPv6 Agent SDK."""
    provider = OpenAIAdapter(
        model=model,
        base_url=lmstudio_url,
        api_key="lm-studio",
    )

    agent = crp.Agent(
        provider=provider,
        tools=[get_weather, convert_temp],
        system="You are a helpful weather assistant.",
        profile="small-local",
    )

    result = agent.run(question)
    return {
        "mode": "CRPv6 AGENT",
        "response": result.answer,
        "tool_used": result.how_it_was_built,
        "governance": {
            "risk": result.crp.risk,
            "grounded": result.crp.grounded,
            "chain_valid": result.crp.chain_valid,
            "audit_url": result.crp.audit_url,
            "operations": result.operations,
            "sources": result.sources,
        },
    }


# ── Side-by-side runner ─────────────────────────────────────────────────────


def run_demo(question: str) -> None:
    print("=" * 70)
    print(f"TASK: {question}")
    print("=" * 70)

    raw = run_raw_llm(question)
    print(f"\n🟦 {raw['mode']}")
    print("-" * 70)
    print(raw["response"])
    print(f"\nTool used: {raw['tool_used']}")
    print(f"Governance: {raw['governance']}")

    crp_result = run_crp_agent(question)
    print(f"\n🟩 {crp_result['mode']}")
    print("-" * 70)
    print(crp_result["response"])
    print(f"\nTool used: {crp_result['tool_used']}")
    print(f"Governance: {json.dumps(crp_result['governance'], indent=2)}")

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Same model, same tools, same question.")
    print(f"Raw LLM returned:      {len(raw['response'].split())} words, no governance.")
    print(f"CRPv6 Agent returned:  {len(crp_result['response'].split())} words, with {len(crp_result['governance']['operations'])} operation(s) and full CRP governance.")


if __name__ == "__main__":
    task = os.environ.get("CRP_DEMO_TASK", "What is the weather in Sydney?")
    run_demo(task)
