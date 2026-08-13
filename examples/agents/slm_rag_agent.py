#!/usr/bin/env python3
# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""SLM-ready RAG agent.

Runs against any OpenAI-compatible endpoint (LM Studio, Ollama, etc.).
Set CRP_LMSTUDIO_URL and CRP_LMSTUDIO_MODEL, or use the defaults.
"""

from __future__ import annotations

import os

import crp
from crp.providers.openai import OpenAIAdapter


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


def main() -> None:
    url = os.environ.get("CRP_LMSTUDIO_URL", "http://localhost:1234/v1")
    model = os.environ.get("CRP_LMSTUDIO_MODEL", "meta-llama-3.1-8b-instruct")

    provider = OpenAIAdapter(model=model, base_url=url, api_key="lm-studio")
    agent = crp.Agent(
        provider=provider,
        tools=[search_documents, read_document],
        system="Answer questions using the provided document corpus.",
        profile="small-local",
    )

    question = "What is CRP and how does it help agentic AI?"
    result = agent.run(question)

    print(f"Q: {question}")
    print(f"A: {result.answer}")
    print(f"Operations: {result.operations}")
    print(f"Risk: {result.crp.risk} | Grounded: {result.crp.grounded} | Chain valid: {result.crp.chain_valid}")
    print(f"Sources: {len(result.sources)}")


if __name__ == "__main__":
    main()
