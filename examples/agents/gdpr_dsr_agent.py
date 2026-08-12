#!/usr/bin/env python3
# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""CRP v6 Agent SDK — GDPR data-subject-request reference agent.

Demonstrates a governed agent where destructive operations (deletion) are
explicitly separated from read-only operations (list, export).  In production
this agent would be backed by a real data store, a policy that gates deletion
behind HITL, and an audit trail that proves the DSR was handled correctly.
"""

from __future__ import annotations

import json
import re
from typing import Any

import crp
from crp.providers.custom import CustomProvider

# ── In-memory user data store ────────────────────────────────────────────────

_STORE: dict[str, dict[str, Any]] = {
    "alice@example.com": {
        "email": "alice@example.com",
        "name": "Alice Smith",
        "logs": ["login 2026-07-01", "query 'CRP pricing' 2026-07-02"],
        "preferences": {"newsletter": True, "theme": "dark"},
    },
    "bob@example.com": {
        "email": "bob@example.com",
        "name": "Bob Jones",
        "logs": ["login 2026-06-28", "scan repo 'acme/web' 2026-07-03"],
        "preferences": {"newsletter": False, "theme": "light"},
    },
}

_PENDING_TOKENS: set[str] = set()


# ── Tools ───────────────────────────────────────────────────────────────────

def list_user_data(email: str) -> dict[str, Any]:
    """Return a summary of the personal data held for ``email``."""
    user = _STORE.get(email)
    if user is None:
        return {"error": "user not found"}
    return {
        "email": user["email"],
        "name": user["name"],
        "record_count": len(user["logs"]) + len(user["preferences"]),
        "categories": ["logs", "preferences"],
    }


def export_user_data(email: str) -> dict[str, Any]:
    """Return a portable export of all data for ``email``."""
    user = _STORE.get(email)
    if user is None:
        return {"error": "user not found"}
    return {"subject": email, "export": user}


def delete_user_data(email: str, request_token: str) -> dict[str, Any]:
    """Delete personal data for ``email`` after validating ``request_token``.

    The ``request_token`` is returned by :func:`request_deletion` and represents
    a deliberate, auditable consent step.  In a production deployment this call
    would also be gated by policy (HITL or automated allow-list) and logged to
    the CRP audit chain.
    """
    user = _STORE.get(email)
    if user is None:
        return {"error": "user not found"}
    if request_token not in _PENDING_TOKENS:
        return {"error": "invalid or missing deletion token"}
    _PENDING_TOKENS.discard(request_token)
    del _STORE[email]
    return {"deleted": True, "subject": email}


def request_deletion(email: str) -> dict[str, Any]:
    """Issue a one-time token required to confirm deletion for ``email``."""
    if email not in _STORE:
        return {"error": "user not found"}
    token = f"dsr-token-{email.split('@')[0]}-delete"
    _PENDING_TOKENS.add(token)
    return {"token": token, "subject": email, "next_step": "call delete_user_data with this token"}


# ── Mock SLM provider ───────────────────────────────────────────────────────


def _mock_generate(messages: list[dict[str, str]]) -> tuple[str, str]:
    prompt = messages[-1]["content"]
    lower = prompt.lower()
    objective_match = re.search(r"objective:\s*(.+)", prompt, re.IGNORECASE)
    objective = (objective_match.group(1).strip() if objective_match else lower).lower()

    email_match = re.search(r"[\w.-]+@[\w.-]+\.\w+", objective)
    email = email_match.group(0) if email_match else "alice@example.com"

    if "delete" in objective or "erase" in objective or "forget" in objective:
        # Deletion requires a token; if not present, request one.
        token_match = re.search(r"dsr-token-[\w-]+", objective)
        if token_match:
            return (
                json.dumps({
                    "capability_id": "delete_user_data",
                    "arguments": {"email": email, "request_token": token_match.group(0)},
                }),
                "stop",
            )
        return (
            json.dumps({
                "capability_id": "request_deletion",
                "arguments": {"email": email},
            }),
            "stop",
        )

    if "export" in objective or "download" in objective or "portable" in objective:
        return (
            json.dumps({
                "capability_id": "export_user_data",
                "arguments": {"email": email},
            }),
            "stop",
        )

    return (
        json.dumps({
            "capability_id": "list_user_data",
            "arguments": {"email": email},
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
    tools=[list_user_data, export_user_data, request_deletion, delete_user_data],
    system=(
        "You are a GDPR data-subject-request handler. You can list and export "
        "data freely. Deletion requires an explicit token from the user; never "
        "delete without it."
    ),
    profile="capable-local",
)


# ── Run ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # List what we hold.
    list_result = agent.run("What data do we hold for alice@example.com?")
    print("List:", list_result.answer)
    print("Operations:", list_result.how_it_was_built)

    # Export the data.
    export_result = agent.run(
        "Export alice@example.com data",
        prior_cso=list_result.cso,
    )
    print("Export:", export_result.answer[:200])
    print("Operations:", export_result.how_it_was_built)

    # Deletion: first request a token, then confirm.
    request = agent.run("Delete alice@example.com data")
    print("Request:", request.answer)

    token = json.loads(request.answer).get("token", "")
    confirm = agent.run(f"Confirm deletion for alice@example.com using token {token}")
    print("Confirm:", confirm.answer)
    print("Operations:", confirm.how_it_was_built)
