#!/usr/bin/env python3
# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""CRP v6 Agent Template — Customer Support Agent.

Triages incoming support tickets, searches a knowledge base, and escalates to
a human when a refund or angry sentiment is detected. Runs against a REAL
model (LM Studio / OpenAI / Anthropic / Ollama — auto-detected).
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import crp
from _shared import resolve_provider

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


provider = resolve_provider()


# ── Agent ───────────────────────────────────────────────────────────────────


def new_agent() -> crp.Agent:
    """Build a fresh agent per independent ticket.

    ``prior_cso=None`` clears the Cognitive State Object (established facts,
    tool observations) between calls, but the ISA layer's turn history and
    session-entity registry (used for intent classification and
    coreference) live on the ``Agent`` instance itself and are NOT reset by
    it. Unrelated tickets need a fresh agent, not just a fresh CSO — reuse
    one agent instance only for genuine multi-turn continuations of the same
    case.
    """
    return crp.Agent(
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
        # A fresh agent per ticket — each is an independent case (see new_agent()).
        result = new_agent().run(f"Classify and handle this ticket: {ticket}")
        print(f"Ticket: {ticket}")
        print(f"  Answer: {result.answer}")
        print(f"  Operations: {result.how_it_was_built}")
        print(f"  Risk: {result.crp.risk}, Grounded: {result.crp.grounded}")
        print()
