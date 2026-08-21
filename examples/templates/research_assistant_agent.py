#!/usr/bin/env python3
# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Flagship template — Research & Knowledge Assistant.

A general-purpose research agent that can search the live web (DuckDuckGo,
no API key required) and read real pages on ANY topic — swap the topic on
the command line and it works unchanged. Runs against a REAL model
(LM Studio / OpenAI / Anthropic / Ollama — auto-detected).

Protocol features this template exercises:

  - Tool Capability Fabric   — `web_search` / `read_page` positioned per turn
  - ISA (intent + coreference) — turn 2 says "the top result" / "it", which
    the agent's built-in coreference resolver ties back to the search results
    established in turn 1, entirely via `prior_cso=` state relay (SPEC-052)
  - CSO / memory relay       — each turn carries forward everything the
                                previous turn established
  - Verification Relay (VR)  — `depth="thorough"` checks the final summary
                                is actually grounded in the fetched page text
  - Quality tiers + sources  — every answer reports a tier and cites which
                                page(s) it came from

Run:
    python examples/templates/research_assistant_agent.py "your topic here"
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import requests
from bs4 import BeautifulSoup

import crp
from _shared import resolve_provider

_UA = "Mozilla/5.0 (compatible; CRP-research-agent/1.0; +https://crprotocol.io)"


def web_search(query: str) -> list[dict]:
    """Search the live web and return the top result titles, URLs, and snippets."""
    try:
        resp = requests.post(
            "https://html.duckduckgo.com/html/",
            data={"q": query},
            headers={"User-Agent": _UA},
            timeout=10,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        return [{"error": f"search failed: {exc}"}]

    soup = BeautifulSoup(resp.text, "html.parser")
    results = []
    for link, snippet in zip(
        soup.select(".result__a")[:5], soup.select(".result__snippet")[:5], strict=False
    ):
        results.append({
            "title": link.get_text(strip=True),
            "url": link.get("href", ""),
            "snippet": snippet.get_text(strip=True) if snippet else "",
        })
    return results or [{"error": "no results"}]


def read_page(url: str) -> str:
    """Fetch a URL and return its main visible text, truncated to ~2000 characters."""
    try:
        resp = requests.get(url, headers={"User-Agent": _UA}, timeout=10)
        resp.raise_for_status()
    except requests.RequestException as exc:
        return f"[could not fetch {url}: {exc}]"

    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(["script", "style", "nav", "header", "footer"]):
        tag.decompose()
    text = " ".join(soup.get_text(separator=" ").split())
    return text[:2000]


def _badge(result: crp.AgentResponse) -> str:
    risk_icon = {"LOW": "🟢", "MEDIUM": "🟡", "HIGH": "🟠", "CRITICAL": "🔴"}.get(result.crp.risk, "⚪")
    return f"{risk_icon} RISK:{result.crp.risk}  GROUNDED:{'✅' if result.crp.grounded else '❌'}"


def main() -> None:
    topic = " ".join(sys.argv[1:]) or "small language models for agentic AI"
    provider = resolve_provider()

    agent = crp.Agent(
        provider=provider,
        tools=[web_search, read_page],
        system=(
            "You are a research assistant. Search the live web, read the most "
            "relevant page, and answer using only what you actually found. "
            "Cite the source URL."
        ),
        profile="capable-local",
        depth="thorough",
    )

    print("=" * 70)
    print(f"TURN 1 — Search for: {topic!r}")
    print("=" * 70)
    turn1 = agent.run(f"Search the web for: {topic}")
    print(f"A: {turn1.answer}\n")
    print(f"Operations: {turn1.how_it_was_built}")
    print(_badge(turn1))
    print(f"Sources: {len(turn1.sources)}")

    print()
    print("=" * 70)
    print("TURN 2 — 'Read the top result' (coreference: 'the top result' → turn 1's search)")
    print("=" * 70)
    turn2 = agent.run("Read the top result and tell me what it says.", prior_cso=turn1.cso)
    print(f"A: {turn2.answer}\n")
    print(f"Operations: {turn2.how_it_was_built}")
    print(_badge(turn2))
    print(f"Sources: {len(turn2.sources)}")

    print()
    print("=" * 70)
    print("TURN 3 — Synthesise a final answer from everything gathered so far")
    print("=" * 70)
    turn3 = agent.run(
        f"Summarise what you found about {topic} in 3-4 sentences, with the source cited.",
        prior_cso=turn2.cso,
    )
    print(f"A: {turn3.answer}\n")
    print(_badge(turn3))
    if turn3.verification:
        print(f"Verification (VR): {turn3.verification}")
    print(f"Quality-relevant facts carried in memory: {len(turn3.cso.established_facts)}")


if __name__ == "__main__":
    main()
