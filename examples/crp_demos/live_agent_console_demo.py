# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Live LM Studio demo for CRPv6 Agent SDK + transparency stream.

Run with LM Studio serving at CRP_LMSTUDIO_URL (default http://192.168.0.6:1234).
"""

from __future__ import annotations

import json
import os
from typing import Any

import crp
from crp.providers.openai import OpenAIAdapter


def get_weather(city: str) -> dict[str, Any]:
    """Return synthetic weather for the requested city."""
    return {"city": city, "temp": 22, "condition": "sunny"}


def run_demo() -> None:
    base_url = os.environ.get("CRP_LMSTUDIO_URL", "http://192.168.0.6:1234/v1")
    provider = OpenAIAdapter(
        model="meta-llama-3.1-8b-instruct",
        base_url=base_url,
        api_key="not-needed",
    )

    agent = crp.Agent(
        provider=provider,
        tools=[get_weather],
        depth="standard",
    )

    print("=" * 70)
    print("CRPv6 Agent SDK — live LM Studio demo")
    print(f"Provider: {base_url}")
    print("=" * 70)

    request = "What's the weather like in Sydney?"
    print(f"\nUser: {request}\n")

    # Collect the transparency stream.
    events: list[dict[str, Any]] = []
    for event in agent.run_tel(request):
        events.append(event.to_dict())

    # Show the final answer (last few text events).
    answer_tokens = [
        e.get("content") or e.get("delta") or ""
        for e in events
        if e.get("type") == "TEXT_MESSAGE_CONTENT"
    ]
    print("Agent:", "".join(answer_tokens).strip())

    print("\n--- Event stream summary ---")
    for e in events:
        etype = e.get("type", "")
        name = e.get("name", "")
        step = e.get("step", "")
        detail = ""
        if etype == "CUSTOM":
            detail = f"name={name} value={json.dumps(e.get('value', {}), default=str)[:90]}"
        elif step:
            detail = f"step={step}"
        elif etype == "TOOL_CALL_START":
            detail = f"tool={e.get('toolCallName')}"
        elif etype == "TOOL_CALL_RESULT":
            detail = f"result={json.dumps(e.get('content', {}), default=str)[:90]}"
        print(f"  {e.get('seq'):>3} {etype:<25} {detail}")

    # Also run with a cognitive preset that adds a reasoning scaffold + safeguard.
    print("\n" + "=" * 70)
    print("Cognitive preset demo — reasoning scaffold + safeguard")
    print("=" * 70)

    preset = {
        "persona": "You are a concise analyst.",
        "reasoning": {
            "phases": [
                {"name": "restate", "prompt": "Restate the core question"},
                {"name": "select_fact", "prompt": "Identify the single most relevant fact"},
                {"name": "answer", "prompt": "Answer in one sentence"},
            ]
        },
        "output": {"format": "paragraph", "length": "short"},
        "safeguards": [
            {
                "name": "no_secrets",
                "scope": "output",
                "condition": "password;secret;key",
                "action": "halt",
                "rationale": "Never reveal credentials.",
            }
        ],
    }
    agent2 = crp.Agent(provider=provider, tools=[], preset=preset)
    result = agent2.run("Summarise what CRP is in one sentence.")
    print(f"\nUser: Summarise what CRP is in one sentence.")
    print(f"Agent: {result.answer}")
    print(f"CRP meta: risk={result.crp.risk} grounded={result.crp.grounded} trust={result.crp.trust_score}")


if __name__ == "__main__":
    run_demo()
