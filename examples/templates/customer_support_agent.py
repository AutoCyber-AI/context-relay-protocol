#!/usr/bin/env python3
# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""CRP v6 Agent Template — Customer Support Agent.

Triages incoming support tickets, searches a knowledge base, and escalates to
a human when a refund or angry sentiment is detected. Runs with a mock SLM
out of the box; swap the provider for production.
"""

from __future__ import annotations

import json
import re

import crp
from crp.providers.custom import CustomProvider

# ── Knowledge base ──────────────────────────────────────────────────────────

_KB: dict[str, str] = {
    "reset-password": "Go to Settings → Security → Change Password. Send a magic-link if email is verified.",
    "billing": "Refunds within 14 days are processed automatically. Escalate charge disputes.",
    "bug-report": "Collect reproduction steps, browser version, and console logs, then open a GitHub issue.",
}


# ── Tools ───────────────────────────────────────────────────────────────────


def classify_ticket(ticket: str) -> dict[str, str]:
    """Classify a support ticket into category and urgency."""
    lower = ticket.lower()
    category = "general"
    if "refund" in lower or "charge" in lower or "billing" in lower:
        category = "billing"
    elif "password" in lower or "login" in lower:
        category = "account"
    elif "bug" in lower or "crash" in lower or "error" in lower:
        category = "bug-report"

    urgency = "low"
    if any(w in lower for w in ("angry", "urgent", "outage", "money", "refund")):
        urgency = "high"
    return {"category": category, "urgency": urgency}


def search_kb(category: str) -> str:
    """Return the knowledge-base article for a ticket category."""
    return _KB.get(category, "No article found. Escalate to a human agent.")


def escalate(reason: str) -> dict[str, str]:
    """Escalate a ticket to a human agent."""
    return {"status": "escalated", "reason": reason, "queue": "tier-2"}


# ── Mock SLM ────────────────────────────────────────────────────────────────


def _mock_generate(messages: list[dict[str, str]]) -> tuple[str, str]:
    prompt = messages[-1]["content"]
    lower = prompt.lower()
    objective_match = re.search(r"objective:\s*(.+)", prompt, re.IGNORECASE)
    objective = (objective_match.group(1).strip() if objective_match else lower).lower()

    if "refund" in objective or "angry" in objective or "escalate" in objective:
        return (
            json.dumps({"capability_id": "escalate", "arguments": {"reason": "high-urgency billing issue"}}),
            "stop",
        )
    if "classify" in objective or "ticket" in objective:
        return (
            json.dumps({"capability_id": "classify_ticket", "arguments": {"ticket": objective}}),
            "stop",
        )
    if "search" in objective or "kb" in objective or "article" in objective:
        category = "billing" if "billing" in objective or "refund" in objective else "general"
        return (
            json.dumps({"capability_id": "search_kb", "arguments": {"category": category}}),
            "stop",
        )

    return (
        json.dumps({"capability_id": None, "answer": "How can I help you today?"}),
        "stop",
    )


provider = CustomProvider(
    generate_fn=_mock_generate,
    count_tokens_fn=lambda text: max(1, len(text.split())),
    context_size=8192,
    name="mock-slm",
)


# ── Agent ───────────────────────────────────────────────────────────────────

agent = crp.Agent(
    provider=provider,
    tools=[classify_ticket, search_kb, escalate],
    system=(
        "You are a customer-support agent. Classify the ticket, search the KB, "
        "and escalate high-urgency or billing disputes to a human."
    ),
    profile="capable-local",
)


# ── Run ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    tickets = [
        "I want a refund — you charged me twice and I'm angry!",
        "How do I reset my password?",
    ]

    for ticket in tickets:
        result = agent.run(f"Classify and handle this ticket: {ticket}")
        print(f"Ticket: {ticket}")
        print(f"  Answer: {result.answer}")
        print(f"  Operations: {result.how_it_was_built}")
        print(f"  Risk: {result.crp.risk}, Grounded: {result.crp.grounded}")
        print()
