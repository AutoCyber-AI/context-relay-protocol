#!/usr/bin/env python3
# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""CRP v6 Agent Template — Code Review Agent.

Reviews a code diff, checks for safety/policy violations, posts feedback, and
gates the IRREVERSIBLE "merge" action behind human-in-the-loop approval — a
real oversight checkpoint, not just a plan-level review. Runs against a REAL
model (LM Studio / OpenAI / Anthropic / Ollama — auto-detected).

Protocol features: Tool Capability Fabric, `oversight_required` +
`clarify_handler` (human approval before `merge_pr` executes), explicit
`Policy`, quality/risk reporting.

Run:
    python examples/templates/code_review_agent.py
"""

from __future__ import annotations

import os
import sys
from typing import Any

sys.path.insert(0, os.path.dirname(__file__))

import crp
from _shared import resolve_provider
from crp.agent_sdk.policy import Policy
from crp.security.clarify import ClarificationAction, ClarificationRequest, ClarificationResolution
from crp.tools.descriptor import SafetyClass

# ── Mock repo state ─────────────────────────────────────────────────────────

_DIFFS: dict[str, str] = {
    "auth.py": (
        "+ def login(password):\n"
        "+     if password == 'admin123':\n"
        "+         return True\n"
    ),
}


# ── Tools ─────────────────────────────────────────────────────────────────


def read_diff(filename: str) -> str:
    """Return the diff for a file."""
    return _DIFFS.get(filename, f"No diff for {filename}")


def run_policy_check(filename: str) -> dict[str, Any]:
    """Run static policy checks on a file's diff and return findings."""
    diff = _DIFFS.get(filename, "")
    lower = diff.lower()
    findings: list[str] = []
    if "select *" in lower and "f'" in lower:
        findings.append("SQL injection risk: string-interpolated query")
    if "admin123" in lower or "password ==" in lower:
        findings.append("Hardcoded credential / weak auth check")
    return {"filename": filename, "violations": findings, "blocked": bool(findings)}


def post_comment(filename: str, comment: str) -> dict[str, str]:
    """Post a review comment on a file."""
    print(f"  [ACTION] 💬 Comment posted on {filename}: {comment!r}")
    return {"filename": filename, "comment": comment, "status": "posted"}


def _merge_pr_impl(filename: str) -> dict[str, str]:
    print(f"  [ACTION] 🔀 [SIMULATED] Merged the change to {filename}.")
    return {"filename": filename, "status": "merged"}


merge_pr_tool = {
    "capability_id": "merge_pr",
    "description": "Merge the pull request. IRREVERSIBLE — ships the change.",
    "impl": _merge_pr_impl,
    "input_schema": {
        "type": "object",
        "properties": {"filename": {"type": "string"}},
        "required": ["filename"],
    },
    "cost_profile": {"safety_class": "destructive"},
}


# ── Human-in-the-loop resolver ──────────────────────────────────────────────

def reviewer_approval_handler(request: ClarificationRequest) -> ClarificationResolution:
    """A real human reviewer's approve/deny decision before a merge executes."""
    print("\n  " + "=" * 60)
    print("  🛑 HUMAN APPROVAL REQUIRED BEFORE MERGE")
    print(f"  Question:  {request.question}")
    print(f"  Context:   {request.context}")
    print("  " + "=" * 60)
    if os.environ.get("CRP_DEMO_DENY") == "1":
        print("  ✋ Reviewer BLOCKED the merge — policy violation found.\n")
        return ClarificationResolution(ClarificationAction.ABORT, answer="denied", reviewer="demo-reviewer")
    print("  ✅ Reviewer approved the merge.\n")
    return ClarificationResolution(ClarificationAction.ANSWER, answer="approve", reviewer="demo-reviewer")


def main() -> None:
    provider = resolve_provider()

    agent = crp.Agent(
        provider=provider,
        tools=[read_diff, run_policy_check, post_comment, merge_pr_tool],
        policy=Policy.balanced(),
        system=(
            "You are a code-review agent. Read the diff, run the policy check, "
            "and post a comment. Never approve or merge changes that fail the "
            "policy check."
        ),
        profile="capable-local",
        oversight_required={SafetyClass.DESTRUCTIVE},
        clarify_handler=reviewer_approval_handler,
    )

    print("=" * 70)
    print("STEP 1 — Review the diff for policy violations")
    print("=" * 70)
    review = agent.run("Read the diff for auth.py and run the policy check on it.")
    print(f"A: {review.answer}\n")
    print(f"Operations: {review.how_it_was_built}")
    print(f"Risk: {review.crp.risk}  Grounded: {review.crp.grounded}")
    print(f"Sources: {len(review.sources)}")

    print()
    print("=" * 70)
    print("STEP 2 — Post the review comment and attempt to merge (HITL gate)")
    print("=" * 70)
    outcome = agent.run(
        "Post a review comment summarising the findings on auth.py, then merge the PR.",
        prior_cso=review.cso,
    )
    print(f"A: {outcome.answer}\n")
    print(f"Operations: {outcome.how_it_was_built}")
    print(f"Halted: {outcome.halted}  Risk: {outcome.crp.risk}")


if __name__ == "__main__":
    main()

