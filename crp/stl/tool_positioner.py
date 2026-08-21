# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Tool Positioner — Operation Frame → Tool Positioning Frame (CRP-SPEC-050 §4.3).

The TCF decides *which* 1–3 capabilities serve the current operation; the Tool
Positioner turns that decision into the minimal prompt fragment the model actually
sees, and parses the model's structured tool-selection output. The model never sees
the full catalogue — only the capabilities the protocol positioned it on.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any

from crp.stl.classifier import STLOperation, operation_to_token
from crp.stl.depth_model import DepthLevel
from crp.stl.frame_builder import OperationFrame
from crp.tools.capability_fabric import CapabilityProfile, CapabilitySelection

logger = logging.getLogger("crp.stl.tool_positioner")


@dataclass
class CapabilitySlot:
    """One capability offered in a Tool Positioning Frame."""

    capability_id: str
    assignment: str
    input_schema: dict[str, Any]
    example_call: dict[str, Any] = field(default_factory=dict)
    output_contract: str = ""


@dataclass
class ToolPositioningFrame:
    """The 1–3 capabilities offered to the model for one operation (CRP-SPEC-050 §4.3)."""

    operation_type: STLOperation
    operation_frame: OperationFrame
    selection_reason: str = ""
    capabilities: list[CapabilitySlot] = field(default_factory=list)
    max_calls: int = 1
    allowed_depth: str = "D3"
    structured_output_mode: str = "json-schema"

    # -- rendering -----------------------------------------------------------

    def to_prompt(self) -> str:
        """Render the operation frame + the offered tools as a compact instruction."""
        lines = [self.operation_frame.to_prompt().rstrip(), ""]
        if not self.capabilities:
            return "\n".join(lines).rstrip()
        lines.append("Available tools for THIS operation (use at most "
                     f"{self.max_calls}; or answer directly if none apply):")
        for i, slot in enumerate(self.capabilities, start=1):
            lines.append(f"{i}. {slot.capability_id} — {slot.assignment}")
            req = slot.input_schema.get("required", [])
            props = list(slot.input_schema.get("properties", {}).keys())
            if props:
                marked = [f"{p}*" if p in req else p for p in props]
                lines.append(f"   args: {', '.join(marked)}  (* = required)")
            if slot.example_call:
                lines.append(f"   example: {json.dumps(slot.example_call, default=str)}")
        lines.extend([
            "",
            "Respond with ONE JSON object and nothing else:",
            '  {"capability_id": "<id>", "arguments": { ... }}',
            'or, if no tool is needed:',
            '  {"capability_id": null, "answer": "<your answer>"}',
        ])
        return "\n".join(lines)

    def output_schema(self) -> dict[str, Any]:
        """JSON schema constraining the model output to a tool selection (for constrained decoding)."""
        ids = [s.capability_id for s in self.capabilities]
        return {
            "type": "object",
            "properties": {
                "capability_id": {"type": ["string", "null"], "enum": [*ids, None]},
                "arguments": {"type": "object"},
                "answer": {"type": "string"},
            },
            "required": ["capability_id"],
            "additionalProperties": False,
        }

    @property
    def capability_ids(self) -> list[str]:
        """Ids of the offered capabilities."""
        return [s.capability_id for s in self.capabilities]


def _example_from_schema(input_schema: dict[str, Any]) -> dict[str, Any]:
    """Build a minimal example call from required properties."""
    props = input_schema.get("properties", {})
    example: dict[str, Any] = {}
    for name in input_schema.get("required", []):
        decl = props.get(name, {})
        t = decl.get("type", "string")
        example[name] = {
            "string": "...", "integer": 0, "number": 0, "boolean": True,
            "array": [], "object": {},
        }.get(t, "...")
    return example


def build_tool_positioning_frame(
    operation_frame: OperationFrame,
    selection: CapabilitySelection,
    *,
    profile: CapabilityProfile = CapabilityProfile.FRONTIER,
    depth: DepthLevel | None = None,
    structured_output_mode: str = "json-schema",
) -> ToolPositioningFrame:
    """Compose a Tool Positioning Frame from an operation frame and a TCF selection."""
    slots: list[CapabilitySlot] = []
    for scored in selection.selected:
        d = scored.descriptor
        if d.description:
            assignment = d.description
        elif d.operation_types:
            assignment = f"Use for {operation_to_token(d.operation_types[0])}."
        else:
            assignment = f"Capability {d.capability_id}."
        slots.append(CapabilitySlot(
            capability_id=d.capability_id,
            assignment=assignment,
            input_schema=d.input_schema,
            example_call=_example_from_schema(d.input_schema),
            output_contract="Return the tool's JSON output only.",
        ))
    # small-local models get one call per operation; larger profiles may chain a couple
    max_calls = 1 if profile is CapabilityProfile.SMALL_LOCAL else min(2, len(slots) or 1)
    return ToolPositioningFrame(
        operation_type=operation_frame.operation_type,
        operation_frame=operation_frame,
        selection_reason=selection.selection_reason,
        capabilities=slots,
        max_calls=max_calls,
        allowed_depth=(depth.value if depth else operation_frame.depth.value),
        structured_output_mode=structured_output_mode,
    )


@dataclass
class ParsedToolCall:
    """A tool selection parsed from the model's output."""

    capability_id: str | None
    arguments: dict[str, Any] = field(default_factory=dict)
    answer: str = ""

    @property
    def is_tool_call(self) -> bool:
        """Whether the model chose a tool (vs answering directly)."""
        return bool(self.capability_id)


def _extract_json_object(text: str) -> dict[str, Any] | None:
    """Best-effort extraction of the first JSON object from model output."""
    text = text.strip()
    # Strip common code fences.
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.MULTILINE).strip()
    try:
        obj = json.loads(text)
        return obj if isinstance(obj, dict) else None
    except (ValueError, TypeError):
        pass
    # Fall back to the first balanced {...} block.
    start = text.find("{")
    while start != -1:
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    candidate = text[start:i + 1]
                    try:
                        obj = json.loads(candidate)
                        if isinstance(obj, dict):
                            return obj
                    except (ValueError, TypeError):
                        break
        start = text.find("{", start + 1)
    return None


def parse_tool_call(raw_output: str, frame: ToolPositioningFrame) -> ParsedToolCall | None:
    """Parse the model's tool-selection output against a positioning frame.

    Returns a :class:`ParsedToolCall`. If the model answered directly (no tool),
    ``capability_id`` is ``None`` and ``answer`` carries the text. Returns ``None``
    only when the output is unparseable AND there is no single obvious capability to
    default to.
    """
    obj = _extract_json_object(raw_output)
    valid_ids = set(frame.capability_ids)

    if obj is None:
        # Unparseable. If exactly one tool was offered, the caller may still answer
        # directly; signal "no structured call" so the loop treats raw as the answer.
        return ParsedToolCall(capability_id=None, answer=raw_output.strip())

    # Tolerate the OpenAI function-calling shape ({"name": ..., "parameters": {...}}).
    # Local SLMs are heavily trained on that convention and slip into it — especially
    # on a second/later tool-offering turn — even when the frame asks for
    # capability_id/arguments; normalize rather than silently discarding the call.
    if obj.get("capability_id") in (None, "", "null") and isinstance(obj.get("name"), str):
        obj = {
            "capability_id": obj["name"],
            "arguments": obj.get("arguments", obj.get("parameters", {})),
        }

    cid = obj.get("capability_id")
    if cid in (None, "", "null"):
        return ParsedToolCall(capability_id=None, answer=str(obj.get("answer", "")).strip())

    if cid not in valid_ids:
        # Hallucinated id — if a single tool was offered, snap to it; else reject.
        if len(valid_ids) == 1:
            cid = next(iter(valid_ids))
        else:
            logger.warning("Model selected unknown capability %r; offered=%s", cid, valid_ids)
            return ParsedToolCall(capability_id=None, answer=str(obj.get("answer", "")).strip())

    args = obj.get("arguments", {})
    if not isinstance(args, dict):
        args = {}
    return ParsedToolCall(capability_id=cid, arguments=args)
