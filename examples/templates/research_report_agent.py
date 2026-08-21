#!/usr/bin/env python3
# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""CRP v6 Agent Template — Research Report Agent.

Demonstrates multi-step research: search sources, read the best match, then
synthesise a report section. CSO carry-forward keeps prior findings across
the retrieval → read → write chain. Runs against a REAL model (LM Studio /
OpenAI / Anthropic / Ollama — auto-detected).

Run:
    python examples/templates/research_report_agent.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import crp
from _shared import resolve_provider

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


# ── Real provider ────────────────────────────────────────────────────────

provider = resolve_provider()


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
    step1 = agent.run("Search for sources about how CRP helps small language models do agentic tasks.")
    print("Step 1:", step1.answer[:300])
    print("Operations:", step1.how_it_was_built)

    step2 = agent.run("Read the most relevant source you found.", prior_cso=step1.cso)
    print("\nStep 2:", step2.answer[:300])
    print("Operations:", step2.how_it_was_built)

    step3 = agent.run(
        "Now write the final report section with citations.",
        prior_cso=step2.cso,
    )
    print("\nStep 3:", step3.answer[:300])
    print("Operations:", step3.how_it_was_built)
    print("Sources used:", len(step3.sources))
