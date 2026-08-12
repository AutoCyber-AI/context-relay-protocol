#!/usr/bin/env python3
# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""CRP v6 Agent Template — Research Report Agent.

Demonstrates multi-step research: search sources, read the best match, then
synthesise a report section. CSO carry-forward keeps prior findings across
the retrieval → read → write chain.
"""

from __future__ import annotations

import json
import re

import crp
from crp.providers.custom import CustomProvider

# ── Mock web index ──────────────────────────────────────────────────────────

_SOURCES: dict[str, str] = {
    "crp-overview": (
        "CRP is a context-relay protocol. It gives each LLM call its own "
        "curated envelope of relevant facts instead of one shared context window."
    ),
    "slm-agentic": (
        "Small language models can be made agentic with the right scaffolding: "
        "intent classification, process reward models, safety classifiers, and "
        "structured tool positioning frames."
    ),
}


# ── Tools ─────────────────────────────────────────────────────────────────


def search_web(query: str) -> list[dict[str, str]]:
    """Search the mock web index and return up to two matching sources."""
    query_lower = query.lower()
    results: list[dict[str, str]] = []
    for source_id, text in _SOURCES.items():
        if any(word in text.lower() for word in query_lower.split() if len(word) > 3):
            results.append({"id": source_id, "title": source_id.replace("-", " ").title(), "excerpt": text[:80]})
        if len(results) >= 2:
            break
    return results


def read_source(source_id: str) -> str:
    """Return the full text of a source by id."""
    return _SOURCES.get(source_id, f"Source {source_id} not found.")


def write_section(heading: str, body: str) -> dict[str, str]:
    """Write a report section and return its metadata."""
    return {"heading": heading, "body": body, "word_count": len(body.split())}


# ── Mock SLM ────────────────────────────────────────────────────────────────


def _mock_generate(messages: list[dict[str, str]]) -> tuple[str, str]:
    prompt = messages[-1]["content"]
    objective_match = re.search(r"objective:\s*(.+)", prompt, re.IGNORECASE)
    objective = (objective_match.group(1).strip() if objective_match else prompt).lower()

    if "search" in objective or "find" in objective:
        return (
            json.dumps({"capability_id": "search_web", "arguments": {"query": objective}}),
            "stop",
        )
    if "read" in objective or "source" in objective:
        sid = "crp-overview" if "crp" in objective else "slm-agentic"
        return (
            json.dumps({"capability_id": "read_source", "arguments": {"source_id": sid}}),
            "stop",
        )
    if "write" in objective or "section" in objective or "report" in objective:
        return (
            json.dumps({"capability_id": "write_section", "arguments": {"heading": "CRP for Agentic SLMs", "body": "CRP positions context per call so SLMs stay coherent across long tasks."}}),
            "stop",
        )

    return (
        json.dumps({"capability_id": None, "answer": "Research complete."}),
        "stop",
    )


provider = CustomProvider(
    generate_fn=_mock_generate,
    count_tokens_fn=lambda text: max(1, len(text.split())),
    context_size=8192,
    name="mock-slm",
)


# ── Agent ─────────────────────────────────────────────────────────────────

agent = crp.Agent(
    provider=provider,
    tools=[search_web, read_source, write_section],
    system=(
        "You are a research assistant. Search for sources, read the most "
        "relevant one, then synthesise a concise report section."
    ),
    profile="capable-local",
    depth="thorough",
)


# ── Run ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    step1 = agent.run("Research how CRP helps small language models do agentic tasks")
    print("Step 1:", step1.answer[:200])
    print("Operations:", step1.how_it_was_built)

    step2 = agent.run(
        "Now write the final report section with citations.",
        prior_cso=step1.cso,
    )
    print("\nStep 2:", step2.answer[:200])
    print("Operations:", step2.how_it_was_built)
    print("Sources used:", len(step2.sources))
