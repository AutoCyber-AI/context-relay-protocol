# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Capability Executor — runs a selected capability and produces a typed observation (CRP-SPEC-050 §6).

The executor is the bridge between a positioned tool selection and effect. It:
  1. validates the model's arguments against the capability ``input_schema``,
  2. invokes the registered implementation,
  3. runs the capability's :class:`ToolResultExtractor` to turn raw output into a
     structured payload (the per-tool-parser pattern — see WASA AI's ``_parse_*``
     functions), and
  4. emits a :class:`ToolObservation` — a typed, provenanced fact destined for the CSO.

Raw output is NEVER returned into the model's window; only the structured observation
is stored (in the CSO) and the raw text is handed to the Scratch Buffer by the caller.
This keeps the working set bounded across hundreds of tool calls (CRP-SPEC-029/030).
"""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from crp.stl.classifier import STLOperation, operation_to_token
from crp.tools.descriptor import CapabilityDescriptor

logger = logging.getLogger("crp.tools.executor")

# A ToolResultExtractor turns a raw capability result + the call args into a
# structured payload (typed facts). Returning the raw value is the default.
ToolResultExtractor = Callable[[Any, dict[str, Any]], Any]


class ExecutionStatus(str, Enum):
    """Outcome of a capability execution."""

    OK = "ok"
    VALIDATION_FAILED = "validation_failed"
    ERROR = "error"
    NOT_REGISTERED = "not_registered"


@dataclass
class ToolObservation:
    """A typed, provenanced fact produced by executing a capability (CRP-SPEC-050 §6.3).

    Designed to convert losslessly into a CSO ``EstablishedFact`` (provenance=TOOL)
    in the Operation State Machine integration step.
    """

    capability_id: str
    operation_type: STLOperation
    payload: Any
    fact_id: str = field(default_factory=lambda: f"f_obs_{uuid.uuid4().hex[:16]}")
    fact_type: str = "TOOL_OBSERVATION"
    invocation_id: str = field(default_factory=lambda: f"inv_{uuid.uuid4().hex[:12]}")
    window_id: str = ""
    grounding_class: str = "CONTEXT_GROUNDED"
    timestamp: float = field(default_factory=time.time)
    scratch_ref: str = ""  # pointer into the Scratch Buffer for the raw output

    def to_dict(self) -> dict[str, Any]:
        """Render the observation as its CRP-SPEC-050 §6.3 JSON form."""
        return {
            "fact_id": self.fact_id,
            "fact_type": self.fact_type,
            "capability_id": self.capability_id,
            "operation_type": operation_to_token(self.operation_type),
            "window_id": self.window_id,
            "provenance": {
                "source_type": "TOOL",
                "source_id": self.capability_id,
                "invocation_id": self.invocation_id,
                "scratch_ref": self.scratch_ref,
                "timestamp": self.timestamp,
            },
            "payload": self.payload,
            "grounding_class": self.grounding_class,
        }


@dataclass
class ToolExecutionResult:
    """The full result of attempting to execute a capability."""

    status: ExecutionStatus
    capability_id: str
    observation: ToolObservation | None = None
    raw_output: Any = None
    errors: list[str] = field(default_factory=list)
    duration_ms: int = 0

    @property
    def ok(self) -> bool:
        """True when execution succeeded and produced an observation."""
        return self.status is ExecutionStatus.OK and self.observation is not None


_TYPE_MAP: dict[str, type | tuple[type, ...]] = {
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
    "array": list,
    "object": dict,
}


def validate_arguments(descriptor: CapabilityDescriptor, args: dict[str, Any]) -> list[str]:
    """Validate call arguments against the capability ``input_schema`` (lightweight subset).

    Checks required keys are present and that declared property types match. Full
    JSON-Schema validation is intentionally out of the zero-dependency core.
    """
    if not isinstance(args, dict):
        return ["arguments must be an object"]
    errors: list[str] = []
    schema = descriptor.input_schema
    for req in descriptor.required_inputs():
        if req not in args:
            errors.append(f"missing required argument: {req}")
    props = schema.get("properties", {}) if isinstance(schema, dict) else {}
    for key, value in args.items():
        prop = props.get(key)
        if isinstance(prop, dict) and "type" in prop:
            expected = _TYPE_MAP.get(prop["type"])
            # bool is a subclass of int — guard so a bool isn't accepted as integer
            if expected and (
                not isinstance(value, expected)
                or (prop["type"] in ("integer", "number") and isinstance(value, bool))
            ):
                errors.append(f"argument {key!r} expected type {prop['type']}")
    return errors


class CapabilityExecutor:
    """Holds capability implementations and executes them into typed observations."""

    def __init__(self) -> None:
        self._impls: dict[str, Callable[[dict[str, Any]], Any]] = {}
        self._extractors: dict[str, ToolResultExtractor] = {}

    def register_impl(
        self,
        capability_id: str,
        fn: Callable[[dict[str, Any]], Any],
        extractor: ToolResultExtractor | None = None,
    ) -> None:
        """Register the implementation (and optional result extractor) for a capability."""
        self._impls[capability_id] = fn
        if extractor is not None:
            self._extractors[capability_id] = extractor

    def has_impl(self, capability_id: str) -> bool:
        """Return whether an implementation is registered for the capability."""
        return capability_id in self._impls

    def execute(
        self,
        descriptor: CapabilityDescriptor,
        args: dict[str, Any],
        operation: STLOperation,
        *,
        window_id: str = "",
    ) -> ToolExecutionResult:
        """Validate, execute, extract, and produce a :class:`ToolObservation`."""
        cid = descriptor.capability_id

        fn = self._impls.get(cid)
        if fn is None:
            return ToolExecutionResult(
                status=ExecutionStatus.NOT_REGISTERED,
                capability_id=cid,
                errors=[f"no implementation registered for {cid!r}"],
            )

        errors = validate_arguments(descriptor, args)
        if errors:
            return ToolExecutionResult(
                status=ExecutionStatus.VALIDATION_FAILED,
                capability_id=cid,
                errors=errors,
            )

        start = time.time()
        try:
            raw = fn(args)
        except Exception as exc:  # noqa: BLE001 — capability failures must be contained
            logger.warning("Capability %r raised: %s", cid, exc)
            return ToolExecutionResult(
                status=ExecutionStatus.ERROR,
                capability_id=cid,
                errors=[f"{type(exc).__name__}: {exc}"],
                duration_ms=int((time.time() - start) * 1000),
            )
        duration_ms = int((time.time() - start) * 1000)

        extractor = self._extractors.get(cid)
        try:
            payload = extractor(raw, args) if extractor else raw
        except Exception as exc:  # noqa: BLE001 — extraction failure falls back to raw
            logger.warning("Extractor for %r raised: %s — using raw payload", cid, exc)
            payload = raw

        observation = ToolObservation(
            capability_id=cid,
            operation_type=operation,
            payload=payload,
            window_id=window_id,
        )
        return ToolExecutionResult(
            status=ExecutionStatus.OK,
            capability_id=cid,
            observation=observation,
            raw_output=raw,
            duration_ms=duration_ms,
        )
