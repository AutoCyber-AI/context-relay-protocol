#!/usr/bin/env python3
# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Live CRPv6 proof against a local SLM.

This script is intentionally small and readable: it shows the same local 8B model
handling tools, RAG, and a long-form task twice — once with a raw prompt and once
through CRPv6. The CRP governance block is printed verbatim so you can see what the
protocol emits in real time.

Set CRP_LMSTUDIO_URL and CRP_LMSTUDIO_MODEL, or rely on the defaults below.
"""

from __future__ import annotations

import json
import os

import crp
from crp.providers.openai import OpenAIAdapter

# -----------------------------------------------------------------------------
# 1. Connect to the local model
# -----------------------------------------------------------------------------

URL = os.environ.get("CRP_LMSTUDIO_URL", "http://localhost:1234/v1")
MODEL = os.environ.get("CRP_LMSTUDIO_MODEL", "meta-llama-3.1-8b-instruct")
print(f"Endpoint: {URL}\nModel:    {MODEL}\n")


def make_provider() -> OpenAIAdapter:
    """Return an OpenAI-compatible provider pointed at LM Studio."""
    return OpenAIAdapter(model=MODEL, base_url=URL, api_key="lm-studio")


# -----------------------------------------------------------------------------
# 2. Define plain-Python tools
# -----------------------------------------------------------------------------


def get_weather(city: str) -> str:
    """Get the current weather for a city."""
    return f"The weather in {city} is 22°C and sunny."


def convert_temp(celsius: float) -> str:
    """Convert Celsius to Fahrenheit."""
    return f"{celsius}°C is {celsius * 9 / 5 + 32:.1f}°F."


_KB = {
    "crp": (
        "CRP (Context Relay Protocol) is a middleware layer that wraps each LLM call. "
        "It builds a positioned envelope of relevant context, selects the right tools, "
        "and carries state forward so small models can run multi-step agentic workflows."
    ),
    "slm": (
        "Small language models can be turned into agents by giving them structured "
        "task intent, filtered tools, and a state relay — instead of dumping everything "
        "into one oversized context window."
    ),
}


def search_kb(query: str) -> list[dict[str, str]]:
    """Search the knowledge base for relevant article ids."""
    words = [w for w in query.lower().split() if len(w) > 2]
    return [
        {"id": k, "excerpt": v[:80] + "..."}
        for k, v in _KB.items()
        if any(w in v.lower() for w in words)
    ][:3]


def read_kb(id: str) -> str:
    """Return the full text of a knowledge base article."""
    return _KB.get(id, "Not found.")


# -----------------------------------------------------------------------------
# 3. Raw LLM arm (no CRP)
# -----------------------------------------------------------------------------


def ask_raw(question: str, tools_description: str) -> str:
    """Ask the model directly with tool descriptions crammed into the prompt."""
    provider = make_provider()
    system = (
        "You are a helpful assistant. You have these tools:\n\n"
        f"{tools_description}\n\n"
        "If you need a tool, output JSON like: "
        '{"tool": "get_weather", "arguments": {"city": "Sydney"}}. '
        "Then stop. The user will give you the tool result. Answer the question."
    )
    output, _ = provider.generate_chat([
        {"role": "system", "content": system},
        {"role": "user", "content": question},
    ])
    return output


# -----------------------------------------------------------------------------
# 4. CRPv6 Agent arm
# -----------------------------------------------------------------------------


def ask_crp(question: str, tools: list, system: str) -> Any:
    """Run the same task through the CRPv6 Agent SDK."""
    provider = make_provider()
    agent = crp.Agent(provider=provider, tools=tools, system=system, profile="small-local")
    return agent.run(question)


def print_crp_result(name: str, result: Any) -> None:
    """Print a CRP result with its full governance block."""
    print(f"\n🟩 CRPv6 — {name}")
    print("-" * 70)
    print(result.answer)
    print("-" * 70)
    governance = {
        "risk": result.crp.risk,
        "grounded": result.crp.grounded,
        "chain_valid": result.crp.chain_valid,
        "operations": result.operations,
        "sources": [
            {
                "fact_id": s.get("fact_id") if isinstance(s, dict) else getattr(s, "fact_id", None),
                "fact_type": s.get("fact_type") if isinstance(s, dict) else getattr(s, "fact_type", None),
                "capability_id": s.get("capability_id") if isinstance(s, dict) else getattr(s, "capability_id", None),
                "operation_type": s.get("operation_type") if isinstance(s, dict) else getattr(s, "operation_type", None),
                "grounding_class": s.get("grounding_class") if isinstance(s, dict) else getattr(s, "grounding_class", None),
                "payload": (s.get("payload", "")[:120] if isinstance(s, dict) else getattr(s, "payload", "")[:120]),
            }
            for s in result.sources
        ],
    }
    print(json.dumps(governance, indent=2, default=str))


# -----------------------------------------------------------------------------
# 5. Run the proofs
# -----------------------------------------------------------------------------


def main() -> None:
    # Case 1: single tool
    print("🟦 RAW LLM — single tool")
    print(ask_raw(
        "What is the weather in Sydney?",
        "get_weather(city: str) -> returns weather in the city."
    ))

    print_crp_result(
        "single tool",
        ask_crp(
            "What is the weather in Sydney?",
            [get_weather, convert_temp],
            "You are a weather assistant.",
        ),
    )

    # Case 2: tool chain
    print("\n🟦 RAW LLM — tool chain")
    print(ask_raw(
        "What is the weather in Sydney and convert it to Fahrenheit?",
        "get_weather(city: str) -> returns weather in Celsius.\n"
        "convert_temp(celsius: float) -> converts Celsius to Fahrenheit.",
    ))

    print_crp_result(
        "tool chain",
        ask_crp(
            "What is the weather in Sydney and convert it to Fahrenheit?",
            [get_weather, convert_temp],
            "You are a weather assistant.",
        ),
    )

    # Case 3: RAG
    print("\n🟦 RAW LLM — RAG")
    print(ask_raw(
        "What is CRP and how does it help small models?",
        "search_kb(query: str) -> returns relevant knowledge base article ids.\n"
        "read_kb(id: str) -> returns full article text.",
    ))

    print_crp_result(
        "RAG retrieval",
        ask_crp(
            "What is CRP and how does it help small models?",
            [search_kb, read_kb],
            "Answer using the knowledge base.",
        ),
    )

    # Case 4: long-form report
    print("\n🟦 RAW LLM — long-form report")
    raw_report = ask_raw(
        "Write a 5-paragraph technical report about the benefits of small local language models. "
        "Each paragraph should cover a different benefit: cost, privacy, latency, offline operation, and sustainability. "
        "Do not repeat headings.",
        "No tools available. Answer directly.",
    )
    print(raw_report[:500])

    crp_report = ask_crp(
        "Write a 5-paragraph technical report about the benefits of small local language models. "
        "Each paragraph should cover a different benefit: cost, privacy, latency, offline operation, and sustainability. "
        "Do not repeat headings.",
        [],
        "You are a technical writer. Produce structured, non-repetitive prose.",
    )
    print_crp_result("long-form report", crp_report)

    print("\n" + "=" * 70)
    print("All CRP results above include runtime governance computed by the protocol.")
    print("No governance values are hardcoded in this script.")
    print("=" * 70)


if __name__ == "__main__":
    main()
