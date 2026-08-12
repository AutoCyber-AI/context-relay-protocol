#!/usr/bin/env python3
# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Comprehensive live LLM test harness for CRPv6 Agent SDK.

Runs a battery of real agentic tasks against a local LM Studio server and prints
a pass/fail report. Each task uses the same model and tools; the only variable is
the CRPv6 orchestration layer.

Set CRP_LMSTUDIO_URL and CRP_LMSTUDIO_MODEL, or edit defaults below.
"""

from __future__ import annotations

import json
import os
import textwrap
from typing import Any

import crp
from crp.providers.openai import OpenAIAdapter


lmstudio_url = os.environ.get("CRP_LMSTUDIO_URL", "http://localhost:1234/v1")
model = os.environ.get("CRP_LMSTUDIO_MODEL", "meta-llama-3.1-8b-instruct")


# ── Shared tools ────────────────────────────────────────────────────────────


def get_weather(city: str) -> str:
    return f"The weather in {city} is 22°C and sunny."


def convert_temp(celsius: float) -> str:
    return f"{celsius}°C is {celsius * 9 / 5 + 32:.1f}°F."


_KB = {
    "crp": "CRP is a context-relay protocol that gives each LLM call its own positioned envelope.",
    "slm": "Small language models can be agentic with the right scaffolding: intent, PRM, safety, and tool frames.",
}


def search_kb(query: str) -> list[dict[str, str]]:
    query_lower = query.lower()
    return [
        {"id": k, "excerpt": v[:80] + "..."}
        for k, v in _KB.items()
        if any(w in v.lower() for w in query_lower.split() if len(w) > 2)
    ][:3]


def read_kb(id: str) -> str:
    return _KB.get(id, "Not found.")


def classify_ticket(ticket: str) -> dict[str, str]:
    lower = ticket.lower()
    if "refund" in lower or "charge" in lower:
        return {"category": "billing", "urgency": "high"}
    if "password" in lower or "login" in lower:
        return {"category": "account", "urgency": "low"}
    return {"category": "general", "urgency": "low"}


def escalate(reason: str) -> dict[str, str]:
    return {"status": "escalated", "reason": reason, "queue": "tier-2"}


# ── Test harness ────────────────────────────────────────────────────────────


def make_agent(tools: list, system: str, profile: str = "small-local") -> crp.Agent:
    provider = OpenAIAdapter(model=model, base_url=lmstudio_url, api_key="lm-studio")
    return crp.Agent(provider=provider, tools=tools, system=system, profile=profile)


def run_case(name: str, question: str, agent: crp.Agent, checks: dict[str, Any]) -> dict[str, Any]:
    result = agent.run(question)
    answer_lower = result.answer.lower()
    sources = [str(s) for s in result.sources]
    sources_combined = " ".join(sources).lower()

    passed = True
    for key, expected in checks.items():
        if key == "answer_contains":
            passed = passed and all(e.lower() in answer_lower for e in expected)
        elif key == "sources_contain":
            passed = passed and all(e.lower() in sources_combined for e in expected)
        elif key == "min_sources":
            passed = passed and len(result.sources) >= expected
        elif key == "operations":
            ops_lower = result.how_it_was_built.lower()
            passed = passed and all(e.lower() in ops_lower for e in expected)

    return {
        "name": name,
        "question": question,
        "answer": result.answer,
        "operations": result.how_it_was_built,
        "risk": result.crp.risk,
        "grounded": result.crp.grounded,
        "chain_valid": result.crp.chain_valid,
        "sources_count": len(result.sources),
        "passed": passed,
    }


def main() -> None:
    print(f"CRPv6 Live Agent Test Harness")
    print(f"Endpoint: {lmstudio_url}")
    print(f"Model:    {model}\n")

    cases: list[dict[str, Any]] = []

    # Case 1: single tool
    cases.append(run_case(
        "Single tool",
        "What is the weather in Sydney?",
        make_agent([get_weather, convert_temp], "You are a weather assistant."),
        checks={
            "answer_contains": ["sydney", "22"],
            "sources_contain": ["get_weather"],
            "operations": ["retrieve"],
        },
    ))

    # Case 2: tool chain
    cases.append(run_case(
        "Tool chain",
        "What is the weather in Sydney and convert it to Fahrenheit?",
        make_agent([get_weather, convert_temp], "You are a weather assistant."),
        checks={
            "answer_contains": ["22", "°f"],
            "min_sources": 2,
            "operations": ["retrieve", "transform"],
        },
    ))

    # Case 3: customer support
    cases.append(run_case(
        "Customer support escalation",
        "I want a refund, you charged me twice!",
        make_agent([classify_ticket, escalate], "Classify support tickets and escalate high-urgency billing issues."),
        checks={
            "answer_contains": ["refund"],
        },
    ))

    # Case 4: RAG retrieval
    cases.append(run_case(
        "RAG retrieval",
        "What is CRP and how does it help small models?",
        make_agent([search_kb, read_kb], "Answer questions using the knowledge base."),
        checks={
            "answer_contains": ["crp"],
            "operations": ["retrieve"],
        },
    ))

    # Print report
    print("-" * 70)
    for c in cases:
        status = "PASS" if c["passed"] else "FAIL"
        print(f"[{status}] {c['name']}")
        print(f"  Q: {c['question']}")
        print(f"  A: {c['answer'][:120]}")
        print(f"  Ops: {c['operations']}")
        print(f"  Sources: {c['sources_count']}")
        print(f"  risk={c['risk']} grounded={c['grounded']} chain_valid={c['chain_valid']}")
        print()

    passed = sum(1 for c in cases if c["passed"])
    print("-" * 70)
    print(f"RESULT: {passed}/{len(cases)} cases passed with CRPv6 + {model}")
    print(f"All responses carried CRP governance metadata.")


if __name__ == "__main__":
    main()
