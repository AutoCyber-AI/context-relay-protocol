#!/usr/bin/env python3
# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""CRP v6 Agent SDK — RAG reference agent.

Demonstrates a document-QA agent that searches an in-memory corpus and then
reads the best match to answer.  The two-run pattern is the same you would use
with a real vector store or CKF graph: first retrieve, then synthesise.
"""

from __future__ import annotations

import json
import re

import crp
from crp.providers.custom import CustomProvider

# ── In-memory corpus ─────────────────────────────────────────────────────────

_CORPUS: dict[str, str] = {
    "doc-1": (
        "CRP is a context-relay protocol for agentic AI. It positions the right "
        "context for each LLM call instead of stuffing everything into one window."
    ),
    "doc-2": (
        "CRP v6 ships three managed models under AutoCyberAI: a SetFit intent "
        "classifier, a DeBERTa process-reward model, and a DeBERTa safety classifier."
    ),
    "doc-3": (
        "The Agent SDK (crp.Agent) lets developers declare tools + policy + model "
        "and runs the positioned loop with structured decoding."
    ),
}


# ── Tools ───────────────────────────────────────────────────────────────────

def search_documents(query: str) -> list[dict[str, str]]:
    """Return up to three matching documents with their ids and excerpts."""
    query_lower = query.lower()
    results: list[dict[str, str]] = []
    for doc_id, text in _CORPUS.items():
        if any(word in text.lower() for word in query_lower.split() if len(word) > 2):
            results.append({"id": doc_id, "excerpt": text[:120] + "..."})
        if len(results) >= 3:
            break
    return results


def read_document(doc_id: str) -> str:
    """Return the full text of a document by id."""
    return _CORPUS.get(doc_id, f"Document {doc_id} not found.")


# ── Mock SLM provider ───────────────────────────────────────────────────────


def _mock_generate(messages: list[dict[str, str]]) -> tuple[str, str]:
    prompt = messages[-1]["content"]
    lower = prompt.lower()
    objective_match = re.search(r"objective:\s*(.+)", prompt, re.IGNORECASE)
    objective = (objective_match.group(1).strip() if objective_match else lower).lower()

    # Retrieval request: any question about CRP or corpus.
    if "search" in objective or "find" in objective or "what" in objective:
        return (
            json.dumps({
                "capability_id": "search_documents",
                "arguments": {"query": objective},
            }),
            "stop",
        )

    # Read request: any mention of a document id.
    doc_match = re.search(r"doc-\d+", objective)
    if doc_match or "read" in objective:
        doc_id = doc_match.group(0) if doc_match else "doc-1"
        return (
            json.dumps({
                "capability_id": "read_document",
                "arguments": {"doc_id": doc_id},
            }),
            "stop",
        )

    return (
        json.dumps({
            "capability_id": None,
            "answer": (
                "CRP positions the right context for each LLM call instead of "
                "stuffing everything into a single window."
            ),
        }),
        "stop",
    )


provider = CustomProvider(
    generate_fn=_mock_generate,
    count_tokens_fn=lambda text: max(1, len(text.split())),
    context_size=8192,
    name="mock-slm",
)


# ── Agent declaration ───────────────────────────────────────────────────────

agent = crp.Agent(
    provider=provider,
    tools=[search_documents, read_document],
    system=(
        "You are a retrieval assistant. Answer questions using only the "
        "provided documents. Cite the document id in your answer."
    ),
    profile="capable-local",
)


# ── Run ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # First run: retrieve candidate documents.
    retrieval = agent.run("Search the corpus for documents about CRP")
    print("Retrieval:", retrieval.answer[:200])
    print("Operations:", retrieval.how_it_was_built)

    # Second run: carry the CSO forward and read the best match.
    synthesis = agent.run(
        "Read doc-1",
        prior_cso=retrieval.cso,
    )
    print("Synthesis:", synthesis.answer[:200])
    print("Operations:", synthesis.how_it_was_built)
