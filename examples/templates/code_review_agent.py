#!/usr/bin/env python3
# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""CRP v6 Agent Template — Code Review Agent.

Reviews a code diff, checks for safety/policy violations, and posts structured
feedback. Demonstrates the CRP safety control plane and checkpoint pattern.
"""

from __future__ import annotations

import json
import re
from typing import Any

import crp
from crp.providers.custom import CustomProvider

# ── Mock repo state ─────────────────────────────────────────────────────────

_DIFFS: dict[str, str] = {
    "auth.py": (
        "+ def login(password):\n"
        "+     if password == 'admin123':\n"
        "+         return True\n"
    ),
    "api.py": (
        "+ def get_user(user_id):\n"
        "+     return db.query(f'SELECT * FROM users WHERE id={user_id}')\n"
    ),
}


# ── Tools ─────────────────────────────────────────────────────────────────


def read_diff(filename: str) -> str:
    """Return the diff for a file."""
    return _DIFFS.get(filename, f"No diff for {filename}")


def run_policy_check(filename: str, diff: str) -> dict[str, Any]:
    """Run static policy checks and return findings."""
    findings: list[str] = []
    lower = diff.lower()
    if "select *" in lower and "f'" in lower:
        findings.append("SQL injection risk: string-interpolated query")
    if "admin123" in lower or "password ==" in lower:
        findings.append("Hardcoded credential / weak auth check")
    return {"filename": filename, "violations": findings, "blocked": bool(findings)}


def post_comment(filename: str, comment: str) -> dict[str, str]:
    """Post a review comment on a file."""
    return {"filename": filename, "comment": comment, "status": "posted"}


# ── Mock SLM ────────────────────────────────────────────────────────────────


def _mock_generate(messages: list[dict[str, str]]) -> tuple[str, str]:
    prompt = messages[-1]["content"]
    objective_match = re.search(r"objective:\s*(.+)", prompt, re.IGNORECASE)
    objective = (objective_match.group(1).strip() if objective_match else prompt).lower()

    # Determine which file we are reviewing.
    if "auth" in objective:
        filename = "auth.py"
    elif "api" in objective or "sql" in objective:
        filename = "api.py"
    else:
        filename = "auth.py"

    if "read" in objective or "diff" in objective:
        return (
            json.dumps({"capability_id": "read_diff", "arguments": {"filename": filename}}),
            "stop",
        )
    if "policy" in objective or "check" in objective:
        return (
            json.dumps({"capability_id": "run_policy_check", "arguments": {"filename": filename, "diff": "placeholder"}}),
            "stop",
        )
    if "comment" in objective or "post" in objective or "review" in objective:
        return (
            json.dumps({"capability_id": "post_comment", "arguments": {"filename": filename, "comment": "CRP safety gate flagged this change."}}),
            "stop",
        )

    return (
        json.dumps({"capability_id": None, "answer": "Review complete — no issues found."}),
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
    tools=[read_diff, run_policy_check, post_comment],
    system=(
        "You are a code-review agent. Read the diff, run the policy check, "
        "and post a comment if any safety violations are found. Never approve "
        "changes that bypass the safety gate."
    ),
    profile="frontier",
)


# ── Run ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    result = agent.run("Review auth.py for security issues")
    print("Review result:", result.answer)
    print("Operations:", result.how_it_was_built)
    print("Safety risk:", result.crp.risk)
    print("Grounded:", result.crp.grounded)
    print("Audit URL:", result.crp.audit_url)
