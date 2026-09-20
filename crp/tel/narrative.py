# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Turn a CRP/AG-UI event stream into a human-readable chain-of-thought narrative.

The :class:`NarrativeBuilder` consumes the same events a frontend would receive
and produces a structured story: what the agent intended, which operations it
chose, which tools it called, what safety and verification checks ran, and how
the provenance chain links each step.  The result can be rendered as Markdown,
HTML, or JSON for consoles, audit UIs, and CLI output.
"""

from __future__ import annotations

import html
import json
from dataclasses import dataclass, field
from typing import Any

from crp.tel.events import Event, EventType


@dataclass
class NarrativeStep:
    """One human-readable step in the agent's reasoning story."""

    kind: str
    title: str
    detail: str = ""
    timestamp: float = 0.0
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "title": self.title,
            "detail": self.detail,
            "timestamp": self.timestamp,
            "meta": self.meta,
        }


@dataclass
class ProvenanceLink:
    """A single link in the HMAC chain rendered for display."""

    op: str
    prev_hash: str
    this_hash: str
    seq: int
    timestamp: float

    def short_prev(self, width: int = 16) -> str:
        return (self.prev_hash or "genesis")[:width]

    def short_this(self, width: int = 16) -> str:
        return self.this_hash[:width]

    def to_dict(self) -> dict[str, Any]:
        return {
            "op": self.op,
            "prev_hash": self.prev_hash,
            "this_hash": self.this_hash,
            "seq": self.seq,
            "timestamp": self.timestamp,
        }


class NarrativeBuilder:
    """Accumulate AG-UI + CRP events and build a readable chain-of-thought.

    Example::

        builder = NarrativeBuilder()
        for event in agent.run_tel("What's the weather in Sydney?"):
            builder.ingest(event)
        story = builder.to_markdown()
    """

    def __init__(self) -> None:
        self.steps: list[NarrativeStep] = []
        self.governance: dict[str, Any] = {
            "risk": "LOW",
            "grounded": False,
            "chain_valid": False,
            "tier": "",
            "confidence": 0.0,
            "semantic_entropy": None,
            "fabrications": 0,
            "sources": 0,
            "invalid_steps": 0,
            "safety_scans": [],
        }
        self.provenance_chain: list[ProvenanceLink] = []
        self.operations: list[str] = []
        self.tool_calls: list[dict[str, Any]] = []
        self._reasoning_buffer: list[str] = []
        self._text_buffer: list[str] = []
        self._current_tool: dict[str, Any] | None = None

    # ------------------------------------------------------------------
    # Ingestion
    # ------------------------------------------------------------------

    def ingest(self, event: Event) -> None:
        """Add one event to the narrative."""
        handler = getattr(self, f"_on_{event.type.value.lower()}", None)
        if handler is not None:
            handler(event)
        elif event.type is EventType.CUSTOM:
            self._on_custom(event)

    def ingest_many(self, events: list[Event]) -> None:
        """Add multiple events in order."""
        for ev in events:
            self.ingest(ev)

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_run_started(self, event: Event) -> None:
        goal = event.payload.get("goal", "")
        self.steps.append(
            NarrativeStep(
                kind="run",
                title="Agent run started",
                detail=f"Goal: {goal}" if goal else "Goal: (user request)",
                timestamp=event.ts,
            )
        )

    def _on_step_started(self, event: Event) -> None:
        step = event.payload.get("step", "")
        if step and step not in self.operations:
            self.operations.append(step)
        self.steps.append(
            NarrativeStep(
                kind="operation",
                title=f"Operation: {step}",
                detail="Positioning the task and selecting the right tools.",
                timestamp=event.ts,
                meta={"operation": step},
            )
        )

    def _on_step_finished(self, event: Event) -> None:
        step = event.payload.get("step", "")
        self.steps.append(
            NarrativeStep(
                kind="operation-done",
                title=f"Operation completed: {step}",
                detail="",
                timestamp=event.ts,
                meta={"operation": step},
            )
        )

    def _on_reasoning_start(self, event: Event) -> None:
        self._reasoning_buffer = []

    def _on_reasoning_content(self, event: Event) -> None:
        delta = event.payload.get("delta", "")
        if delta:
            self._reasoning_buffer.append(delta)

    def _on_reasoning_end(self, event: Event) -> None:
        self._flush_reasoning(event.ts)

    def _flush_reasoning(self, ts: float | None = None) -> None:
        """Materialise any buffered reasoning deltas as a narrative step."""
        text = "".join(self._reasoning_buffer).strip()
        if text:
            self.steps.append(
                NarrativeStep(
                    kind="reasoning",
                    title="Thinking",
                    detail=text,
                    timestamp=ts if ts is not None else 0.0,
                )
            )
        self._reasoning_buffer = []

    def _on_tool_call_start(self, event: Event) -> None:
        name = event.payload.get("toolCallName", "")
        reason = event.payload.get("reason", "")
        call_id = event.payload.get("toolCallId", "")
        self._current_tool = {
            "call_id": call_id,
            "name": name,
            "reason": reason,
            "args": "",
            "result": None,
        }
        detail = f"Selected tool: {name}"
        if reason:
            detail += f" for operation: {reason}"
        self.steps.append(
            NarrativeStep(
                kind="tool-select",
                title=f"Tool selected — {name}",
                detail=detail,
                timestamp=event.ts,
                meta={"tool": name, "call_id": call_id, "reason": reason},
            )
        )

    def _on_tool_call_args(self, event: Event) -> None:
        delta = event.payload.get("delta", "")
        if self._current_tool is not None:
            self._current_tool["args"] += delta

    def _on_tool_call_end(self, event: Event) -> None:
        if self._current_tool is not None:
            args = self._current_tool["args"]
            try:
                parsed = json.loads(args) if args else {}
            except json.JSONDecodeError:
                parsed = {"raw": args}
            self.steps.append(
                NarrativeStep(
                    kind="tool-call",
                    title=f"Calling {self._current_tool['name']}",
                    detail=json.dumps(parsed, indent=2, default=str) if parsed else "(no arguments)",
                    timestamp=event.ts,
                    meta={"tool": self._current_tool["name"], "args": parsed},
                )
            )

    def _on_tool_call_result(self, event: Event) -> None:
        content = event.payload.get("content", "")
        call_id = event.payload.get("toolCallId", "")
        if self._current_tool is not None and self._current_tool.get("call_id") == call_id:
            self._current_tool["result"] = content
        summary = self._summarise_result(content)
        self.steps.append(
            NarrativeStep(
                kind="tool-result",
                title="Tool result received",
                detail=summary,
                timestamp=event.ts,
                meta={"tool": self._current_tool["name"] if self._current_tool else "", "call_id": call_id},
            )
        )
        if self._current_tool is not None:
            self.tool_calls.append(self._current_tool.copy())
        self._current_tool = None

    def _on_text_message_start(self, event: Event) -> None:
        # Reasoning deltas may arrive without a closing REASONING_END; flush them
        # before the answer begins so they are not lost.
        self._flush_reasoning()
        self._text_buffer = []

    def _on_text_message_content(self, event: Event) -> None:
        data = event.payload.get("data", {}) or {}
        content = ""
        if isinstance(data, dict):
            content = data.get("content", "")
        if not content:
            # Some emitters stream the delta directly in the payload.
            content = event.payload.get("delta", "")
        if content:
            self._text_buffer.append(content)

    def _on_text_message_end(self, event: Event) -> None:
        self._flush_text(event.ts)

    def _flush_text(self, ts: float | None = None) -> None:
        """Materialise any buffered answer tokens as a narrative step."""
        text = "".join(self._text_buffer).strip()
        if text:
            self.steps.append(
                NarrativeStep(
                    kind="answer",
                    title="Final answer",
                    detail=text,
                    timestamp=ts if ts is not None else 0.0,
                )
            )
        self._text_buffer = []

    def _on_state_snapshot(self, event: Event) -> None:
        snapshot = event.payload.get("snapshot", {})
        facts = snapshot.get("established_facts", [])
        if facts:
            self.steps.append(
                NarrativeStep(
                    kind="memory",
                    title="Memory snapshot",
                    detail=f"{len(facts)} established fact(s) carried forward.",
                    timestamp=event.ts,
                    meta={"facts": len(facts)},
                )
            )

    def _on_run_finished(self, event: Event) -> None:
        self._flush_reasoning(event.ts)
        self._flush_text(event.ts)
        self.steps.append(
            NarrativeStep(
                kind="run-done",
                title="Run finished",
                detail="Governance summary available.",
                timestamp=event.ts,
            )
        )

    def _on_run_error(self, event: Event) -> None:
        self._flush_reasoning(event.ts)
        self._flush_text(event.ts)
        self.steps.append(
            NarrativeStep(
                kind="error",
                title="Run halted",
                detail=event.payload.get("error", "Unknown error"),
                timestamp=event.ts,
                meta={"error": event.payload.get("error", "")},
            )
        )

    def _on_interrupt(self, event: Event) -> None:
        reason = event.payload.get("reason", "")
        action = event.payload.get("action", {})
        self.steps.append(
            NarrativeStep(
                kind="interrupt",
                title="Human oversight required",
                detail=reason,
                timestamp=event.ts,
                meta={"action": action},
            )
        )

    def _on_custom(self, event: Event) -> None:
        name = event.payload.get("name", "")
        value = event.payload.get("value", {})
        if name == "crp.intent":
            ops = value.get("plan", [])
            detail = f"Detected intent: {value.get('detail', '')}"
            if ops:
                detail += f" → planned operations: {', '.join(str(o) for o in ops)}"
            self.steps.append(
                NarrativeStep(
                    kind="intent",
                    title="Intent classified",
                    detail=detail,
                    timestamp=event.ts,
                    meta=value,
                )
            )
        elif name == "crp.safety_scan":
            self.governance["safety_scans"].append(value)
            risk = value.get("risk", "LOW")
            detail = f"Stage: {value.get('stage', '')}; verdict: {value.get('verdict', '')}"
            self.steps.append(
                NarrativeStep(
                    kind="safety",
                    title=f"Safety scan — {risk}",
                    detail=detail,
                    timestamp=event.ts,
                    meta=value,
                )
            )
        elif name == "crp.quality":
            self.governance["tier"] = value.get("tier", "")
            self.governance["confidence"] = value.get("confidence", 0.0)
            if "semantic_entropy" in value:
                self.governance["semantic_entropy"] = value["semantic_entropy"]
            self.steps.append(
                NarrativeStep(
                    kind="quality",
                    title=f"Quality tier: {value.get('tier', '')}",
                    detail=f"Confidence: {value.get('confidence', 0.0):.2f}",
                    timestamp=event.ts,
                    meta=value,
                )
            )
        elif name == "crp.verification":
            self.governance["invalid_steps"] = value.get("invalid", 0)
            self.steps.append(
                NarrativeStep(
                    kind="verification",
                    title="Verification relay",
                    detail=f"Invalid steps: {value.get('invalid', 0)}; repairs: {value.get('repairs', 0)}",
                    timestamp=event.ts,
                    meta=value,
                )
            )
        elif name == "crp.retrieval":
            sources = value.get("sources", [])
            self.governance["sources"] = len(sources)
            self.steps.append(
                NarrativeStep(
                    kind="retrieval",
                    title="Retrieval",
                    detail=f"{len(sources)} source(s) identified.",
                    timestamp=event.ts,
                    meta=value,
                )
            )
        elif name == "crp.provenance":
            link = ProvenanceLink(
                op=value.get("op", ""),
                prev_hash=value.get("prev", ""),
                this_hash=value.get("hash", ""),
                seq=event.seq,
                timestamp=event.ts,
            )
            self.provenance_chain.append(link)
            self.governance["chain_valid"] = True
            self.steps.append(
                NarrativeStep(
                    kind="provenance",
                    title="Provenance link added",
                    detail=f"{link.short_prev()} → {link.short_this()}",
                    timestamp=event.ts,
                    meta=link.to_dict(),
                )
            )
        elif name == "crp.policy":
            self.steps.append(
                NarrativeStep(
                    kind="policy",
                    title="Policy envelope checked",
                    detail=f"Verdict: {value.get('verdict', 'allow')}",
                    timestamp=event.ts,
                    meta=value,
                )
            )
        elif name == "crp.run_complete":
            self.steps.append(
                NarrativeStep(
                    kind="run-complete",
                    title="Positioned loop complete",
                    detail=value.get("detail", ""),
                    timestamp=event.ts,
                    meta=value,
                )
            )
        elif name == "crp.governance":
            self.governance.update(value)
            self.steps.append(
                NarrativeStep(
                    kind="governance",
                    title="Governance summary",
                    detail=f"risk={value.get('risk', '?')}, grounded={value.get('grounded', '?')}, chain_valid={value.get('chain_valid', '?')}",
                    timestamp=event.ts,
                    meta=value,
                )
            )
        elif name == "crp.progress":
            percent = value.get("percent", 0)
            current = value.get("current", "")
            self.steps.append(
                NarrativeStep(
                    kind="progress",
                    title=f"Progress: {percent}%",
                    detail=current,
                    timestamp=event.ts,
                    meta=value,
                )
            )

    # ------------------------------------------------------------------
    # Output formats
    # ------------------------------------------------------------------

    def _summarise_result(self, content: Any) -> str:
        """Return a short, human-readable summary of a tool result."""
        if content is None:
            return "(empty result)"
        if isinstance(content, str):
            text = content.strip()
            return text[:280] + ("…" if len(text) > 280 else "")
        if isinstance(content, dict):
            text = json.dumps(content, default=str)
            return text[:280] + ("…" if len(text) > 280 else "")
        return str(content)[:280]

    def to_dict(self) -> dict[str, Any]:
        """Return the full narrative as a JSON-serialisable dict."""
        return {
            "steps": [s.to_dict() for s in self.steps],
            "governance": self.governance,
            "provenance_chain": [p.to_dict() for p in self.provenance_chain],
            "operations": self.operations,
            "tool_calls": self.tool_calls,
        }

    def to_markdown(self) -> str:
        """Render the narrative as Markdown."""
        lines: list[str] = ["# CRP Run Narrative\n"]
        for step in self.steps:
            lines.append(f"## {step.title}")
            lines.append(f"*{step.kind}* — {step.detail}\n")
        lines.append("## Governance Summary")
        for key, val in self.governance.items():
            lines.append(f"- **{key}**: {val}")
        if self.provenance_chain:
            lines.append("\n## Provenance Chain")
            for link in self.provenance_chain:
                lines.append(f"- `{link.short_prev()}` → `{link.short_this()}` ({link.op})")
        return "\n".join(lines)

    def to_html(self) -> str:
        """Render the narrative as a safe HTML fragment for consoles."""
        out: list[str] = ['<div class="crp-narrative">']
        for step in self.steps:
            safe_title = html.escape(str(step.title))
            safe_detail = html.escape(str(step.detail)).replace("\n", "<br>")
            out.append(
                f'<div class="crp-narrative-step crp-narrative-step--{html.escape(step.kind)}">'
                f'<div class="crp-narrative-title">{safe_title}</div>'
                f'<div class="crp-narrative-detail">{safe_detail}</div>'
                '</div>'
            )
        out.append('</div>')
        return "\n".join(out)
