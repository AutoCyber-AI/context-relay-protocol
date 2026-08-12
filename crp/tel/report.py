# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Localized transparency reports from an event buffer (CRP-SPEC-056 §8.3)."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from crp.tel.events import Event, EventType

# Disclosure tiers from The Architecture of Transparency, Chapter 4.
_TIERS = {"casual", "power", "developer", "auditor"}


def build_report(buffer: Iterable[Event], tier: str = "casual") -> dict[str, Any]:
    """Build a human-readable transparency report from an event buffer.

    The same event stream drives all tiers; ``tier`` is a rendering filter, not
    a different backend. ``casual`` returns narrative + governance badges;
    ``power`` adds tools and sources; ``developer`` adds the raw event log;
    ``auditor`` adds the full provenance chain.
    """
    tier = tier.lower()
    if tier not in _TIERS:
        tier = "casual"

    events = list(buffer)
    narrative_parts: list[str] = []
    tools: list[dict[str, Any]] = []
    governance: list[dict[str, Any]] = []
    audit_hashes: list[dict[str, str]] = []
    state: dict[str, Any] | None = None
    current_tool: dict[str, Any] | None = None

    for ev in events:
        if ev.type is EventType.TEXT_MESSAGE_CONTENT:
            narrative_parts.append(str(ev.payload.get("delta", "")))

        elif ev.type is EventType.TOOL_CALL_START:
            current_tool = {
                "id": ev.payload.get("toolCallId"),
                "name": ev.payload.get("toolCallName"),
                "reason": ev.payload.get("reason"),
                "args": "",
                "result": None,
            }
            tools.append(current_tool)

        elif ev.type is EventType.TOOL_CALL_ARGS and current_tool is not None:
            current_tool["args"] += str(ev.payload.get("delta", ""))

        elif ev.type is EventType.TOOL_CALL_RESULT:
            tid = ev.payload.get("toolCallId")
            for t in tools:
                if t["id"] == tid:
                    t["result"] = ev.payload.get("content")
                    break

        elif ev.type is EventType.CUSTOM:
            name = ev.payload.get("name")
            value = ev.payload.get("value")
            governance.append({"name": name, "value": value})
            if name == "crp.provenance" and isinstance(value, dict):
                audit_hashes.append(
                    {"op": value.get("op", ""), "hash": value.get("hash", "")}
                )

        elif ev.type is EventType.STATE_SNAPSHOT:
            state = ev.payload.get("snapshot")

        elif ev.type is EventType.STATE_DELTA:
            state = state or {}
            # Lightweight delta apply for common ops; full RFC-6902 is optional.
            for op in ev.payload.get("delta", []):
                _apply_patch(state, op)

    report: dict[str, Any] = {
        "tier": tier,
        "event_count": len(events),
        "summary": _summarise(events),
    }

    narrative = "".join(narrative_parts).strip()
    if narrative:
        report["narrative"] = narrative

    if tier in {"casual", "power", "developer", "auditor"}:
        report["governance"] = _governance_badge_view(governance)

    if tier in {"power", "developer", "auditor"}:
        report["tools"] = tools
        if state is not None:
            report["state"] = state

    if tier in {"developer", "auditor"}:
        report["raw_events"] = [ev.to_dict() for ev in events]

    if tier == "auditor":
        report["audit_chain"] = audit_hashes

    return report


def _summarise(events: list[Event]) -> str:
    started = any(e.type is EventType.RUN_STARTED for e in events)
    finished = any(e.type is EventType.RUN_FINISHED for e in events)
    errored = any(e.type is EventType.RUN_ERROR for e in events)
    tool_count = sum(1 for e in events if e.type is EventType.TOOL_CALL_START)
    if errored:
        status = "halted"
    elif finished:
        status = "completed"
    elif started:
        status = "in progress"
    else:
        status = "unknown"
    return f"Run {status} with {tool_count} tool call(s) and {len(events)} event(s)."


def _governance_badge_view(governance: list[dict[str, Any]]) -> dict[str, Any]:
    """Surface the most recent value for each governance badge."""
    badges: dict[str, Any] = {}
    for g in governance:
        name = g.get("name")
        if name:
            badges[name] = g.get("value")
    return badges


def _apply_patch(state: dict[str, Any], op: dict[str, Any]) -> None:
    """Apply a tiny subset of RFC-6902 for the report's live state mirror."""
    path = op.get("path", "")
    operation = op.get("op")
    if not path or not operation:
        return
    parts = [p for p in path.split("/") if p]
    target: Any = state
    for part in parts[:-1]:
        if part not in target or not isinstance(target[part], dict):
            target[part] = {}
        target = target[part]
    key = parts[-1] if parts else ""
    if key == "-" and operation == "add":
        if not isinstance(target, list):
            # Convert the dict slot into a list (common "add to array" pattern).
            parent_key = parts[-2] if len(parts) >= 2 else None
            target = []
            if parent_key is not None:
                state[parent_key] = target
        target.append(op.get("value"))
    elif operation == "add" or operation == "replace":
        target[key] = op.get("value")
    elif operation == "remove" and key in target:
        del target[key]
