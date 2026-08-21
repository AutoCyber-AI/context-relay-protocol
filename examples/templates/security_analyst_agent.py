#!/usr/bin/env python3
# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Flagship template — Security Analyst / SOC Triage Agent.

A real-world blue-team workflow: triage a vulnerability finding, correlate it
against threat intelligence, then decide whether to remediate. Runs against a
REAL model (LM Studio / OpenAI / Anthropic / Ollama — auto-detected) so the
governance metadata below is genuine, not scripted.

This template deliberately exercises the protocol surface a SOC/pentest agent
needs and a *toy* agent usually skips:

  - Tool Capability Fabric   — read-only recon tools positioned per operation
  - Human-in-the-loop gate   — `oversight_required` + `clarify_handler` halt
                                and re-route a DESTRUCTIVE action (quarantine)
                                to a human approval step *before* it executes,
                                not just at plan-review time
  - Verification Relay (VR)  — `depth="thorough"` runs grounding/step checks
  - CSO / memory relay       — the remediation turn carries forward everything
                                the triage turn established (`prior_cso=`)
  - Transparency stream      — `run_tel()` emits the AG-UI + `crp.*` governance
                                event sequence live (reasoning, tool calls,
                                quality tier, provenance) for the remediation step
  - Explicit Policy          — a constructed `Policy`, not the implicit default

Lessons folded in from a prior large-scale pentest-agent integration audit:
ONE tool registry (no duplicate/ambiguous tool defs), ONE positioned loop (no
competing orchestrators), and destructive actions gated at *call time*, not
just plan time — see AGENTS.md for the source audit this template responds to.

Run:
    python examples/templates/security_analyst_agent.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import crp
from _shared import resolve_provider
from crp.agent_sdk.policy import Policy
from crp.security.clarify import ClarificationAction, ClarificationRequest, ClarificationResolution
from crp.tools.descriptor import SafetyClass

# ── Read-only recon tools (SafetyClass.READ_ONLY / NETWORK by default) ─────

_CVE_DB = {
    ("apache", "2.4.49"): {
        "cve": "CVE-2021-41773",
        "severity": "CRITICAL",
        "summary": "Path traversal / RCE in Apache HTTP Server 2.4.49",
    },
    ("openssh", "8.2"): {
        "cve": "CVE-2020-14145",
        "severity": "MEDIUM",
        "summary": "Client information leak during banner exchange",
    },
}

_THREAT_INTEL_DB = {
    "10.0.0.15": {"reputation": "malicious", "seen_in_feeds": ["abuse.ch", "spamhaus"], "score": 92},
    "10.0.0.20": {"reputation": "clean", "seen_in_feeds": [], "score": 3},
}


def lookup_cve(service: str, version: str) -> dict:
    """Look up known CVEs for a service and version."""
    hit = _CVE_DB.get((service.lower(), version))
    return hit or {"cve": None, "severity": "UNKNOWN", "summary": "No known CVE on file."}


def check_threat_intel(ip: str) -> dict:
    """Check an IP address against threat-intelligence feeds."""
    return _THREAT_INTEL_DB.get(ip, {"reputation": "unknown", "seen_in_feeds": [], "score": 0})


def notify_security_team(message: str) -> dict:
    """Send an alert to the on-call security team (mutating, non-destructive)."""
    print(f"  [ACTION] 📟 Paged on-call SOC: {message!r}")
    return {"status": "sent", "channel": "#soc-oncall"}


# ── The gated, destructive action ───────────────────────────────────────────
# Passed as a dict (not a bare callable) so it can carry BOTH a real
# implementation ("impl") AND an explicit, non-default safety_class — the
# only way to attach both through the public tools=[...] surface.

def _quarantine_host_impl(ip: str, reason: str) -> dict:
    print(f"  [ACTION] 🔒 [SIMULATED] Host {ip} isolated from the network. Reason: {reason}")
    return {"status": "quarantined", "ip": ip, "reason": reason}


quarantine_host_tool = {
    "capability_id": "quarantine_host",
    "description": "Isolate a host from the network. IRREVERSIBLE without manual network re-admission.",
    "impl": _quarantine_host_impl,
    "input_schema": {
        "type": "object",
        "properties": {"ip": {"type": "string"}, "reason": {"type": "string"}},
        "required": ["ip", "reason"],
    },
    "cost_profile": {"safety_class": "destructive"},
}


# ── Human-in-the-loop resolver ──────────────────────────────────────────────

def soc_approval_handler(request: ClarificationRequest) -> ClarificationResolution:
    """Resolve an oversight/clarification request.

    In production this would page a human (Slack button, PagerDuty, a web
    console) and block on their reply. For this template it prints the exact
    approval prompt an analyst would see and auto-approves after a visible
    pause, unless CRP_DEMO_DENY=1 is set (to show the deny/halt path too).
    """
    print("\n  " + "=" * 60)
    print("  🛑 HUMAN APPROVAL REQUIRED")
    print(f"  Reason:    {request.reason}")
    print(f"  Question:  {request.question}")
    print(f"  Context:   {request.context}")
    print("  " + "=" * 60)
    if os.environ.get("CRP_DEMO_DENY") == "1":
        print("  ✋ Analyst DENIED the action (CRP_DEMO_DENY=1).\n")
        return ClarificationResolution(ClarificationAction.ABORT, answer="denied", reviewer="demo-analyst")
    print("  ✅ Analyst APPROVED the action.\n")
    return ClarificationResolution(ClarificationAction.ANSWER, answer="approve", reviewer="demo-analyst")


def _badge(result: crp.AgentResponse) -> str:
    risk_icon = {"LOW": "🟢", "MEDIUM": "🟡", "HIGH": "🟠", "CRITICAL": "🔴"}.get(result.crp.risk, "⚪")
    grounded_icon = "✅" if result.crp.grounded else "❌"
    chain_icon = "🔗✅" if result.crp.chain_valid else "🔗❌"
    return f"{risk_icon} RISK:{result.crp.risk}  GROUNDED:{grounded_icon}  CHAIN:{chain_icon}"


def main() -> None:
    provider = resolve_provider()

    policy = Policy.balanced().domain("security")

    agent = crp.Agent(
        provider=provider,
        tools=[lookup_cve, check_threat_intel, notify_security_team, quarantine_host_tool],
        policy=policy,
        system=(
            "You are a SOC security analyst assistant. Use the available tools to "
            "investigate findings before recommending or taking action. Never "
            "claim an action succeeded unless a tool actually reported it."
        ),
        profile="capable-local",
        depth="thorough",  # enables Verification Relay (VR) grounding checks
        oversight_required={SafetyClass.DESTRUCTIVE},
        clarify_handler=soc_approval_handler,
    )

    print("=" * 70)
    print("STEP 1 — Look up the vulnerability")
    print("=" * 70)
    step1 = agent.run(
        "A scan found Apache 2.4.49 running on host 10.0.0.15. Look up any known CVE for it."
    )
    print(f"A: {step1.answer}\n")
    print(f"Operations: {step1.how_it_was_built}")
    print(_badge(step1))
    if step1.verification:
        print(f"Verification (VR): {step1.verification}")
    print(f"Sources: {len(step1.sources)}")
    for s in step1.sources:
        print(f"  - {s.get('capability_id')}: {s.get('payload')}")

    print()
    print("=" * 70)
    print("STEP 2 — Check the host's reputation (note: 'that host' — coreference)")
    print("=" * 70)
    step2 = agent.run(
        "Now check the threat-intelligence reputation of that host.",
        prior_cso=step1.cso,
    )
    print(f"A: {step2.answer}\n")
    print(f"Operations: {step2.how_it_was_built}")
    print(_badge(step2))
    print(f"Sources: {len(step2.sources)}")
    for s in step2.sources:
        print(f"  - {s.get('capability_id')}: {s.get('payload')}")

    print()
    print("=" * 70)
    print("STEP 3 — Decide remediation (triggers the human-oversight gate)")
    print("=" * 70)
    remediation_events = 0
    for ev in agent.run_tel(
        "Produce the remediation now: quarantine the host and notify the security team.",
        prior_cso=step2.cso,
    ):
        remediation_events += 1
        kind = getattr(getattr(ev, "type", None), "value", ev.type)
        payload = getattr(ev, "payload", {}) or {}
        print(f"  [{remediation_events:02d}] {kind:<22} {payload}")

    print(f"\n{remediation_events} transparency events streamed for the remediation step.")


if __name__ == "__main__":
    main()
