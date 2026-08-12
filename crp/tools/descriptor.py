# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Capability Descriptor — machine-readable declaration of a TCF capability (CRP-SPEC-050 §3).

A capability may be a local function, an MCP tool, a sub-agent, a database query, or a
web service. The descriptor tells the protocol which STL operations the capability
serves, what it consumes/produces, its cost, and how it is governed — so the Tool
Capability Fabric can select it for an operation WITHOUT injecting its schema into the
model's prompt (positioning, not injection).

The canonical JSON form is ``schemas/capability-descriptor.json``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from crp.stl.classifier import STLOperation, operation_from_token, operation_to_token

logger = logging.getLogger("crp.tools.descriptor")


class CapabilityKind(str, Enum):
    """Runtime kind of a capability (CRP-SPEC-050 §3.2)."""

    TOOL = "tool"
    MCP_TOOL = "mcp-tool"
    AGENT = "agent"
    QUERY = "query"
    SERVICE = "service"


class SafetyClass(str, Enum):
    """Safety classification used for policy pre-filtering (CRP-SPEC-050 §3.4)."""

    READ_ONLY = "read-only"
    MUTATING = "mutating"
    DESTRUCTIVE = "destructive"
    NETWORK = "network"
    HUMAN_OVERSIGHT = "human-oversight"


@dataclass
class CostProfile:
    """Estimated cost of invoking a capability (CRP-SPEC-050 §3.1)."""

    tokens: int = 0
    latency_ms: int = 0
    safety_class: SafetyClass = SafetyClass.READ_ONLY

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CostProfile:
        """Build a CostProfile from its JSON form."""
        raw_class = data.get("safety_class", "read-only")
        try:
            safety = SafetyClass(raw_class)
        except ValueError:
            logger.warning("Unknown safety_class %r — defaulting to read-only", raw_class)
            safety = SafetyClass.READ_ONLY
        return cls(
            tokens=int(data.get("tokens", 0)),
            latency_ms=int(data.get("latency_ms", 0)),
            safety_class=safety,
        )

    def to_dict(self) -> dict[str, Any]:
        """Render the CostProfile as its JSON form."""
        return {
            "tokens": self.tokens,
            "latency_ms": self.latency_ms,
            "safety_class": self.safety_class.value,
        }


@dataclass
class CapabilityDescriptor:
    """A single capability registered in the Tool Capability Fabric (CRP-SPEC-050 §3.1).

    ``operation_types`` is stored as canonical :class:`STLOperation` members; the
    JSON form uses uppercase tokens (``RETRIEVE`` …) normalised on load.
    """

    capability_id: str
    kind: CapabilityKind = CapabilityKind.TOOL
    version: str = "1.0.0"
    operation_types: list[STLOperation] = field(default_factory=list)
    input_schema: dict[str, Any] = field(default_factory=dict)
    output_schema: dict[str, Any] = field(default_factory=dict)
    produces_facts: bool = True
    cost_profile: CostProfile = field(default_factory=CostProfile)
    serves_intents: list[str] = field(default_factory=list)
    consumes_facts: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    mutually_exclusive_with: list[str] = field(default_factory=list)
    data_residency: str = ""
    allowed_policy_domains: list[str] = field(default_factory=list)
    embedding_vector: list[float] | None = None
    embedding_model: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------------ helpers

    @property
    def description(self) -> str:
        """Human-readable description from metadata, if present."""
        return str(self.metadata.get("description", ""))

    def serves_operation(self, op: STLOperation) -> bool:
        """Return whether this capability serves the given cognitive operation."""
        return op in self.operation_types

    def required_inputs(self) -> list[str]:
        """Return the required argument names declared in ``input_schema``."""
        req = self.input_schema.get("required", [])
        return list(req) if isinstance(req, list) else []

    # ------------------------------------------------------------- (de)serialise

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CapabilityDescriptor:
        """Build a descriptor from its JSON form, normalising operation tokens.

        Unknown operation tokens are dropped with a warning rather than raising,
        so a single bad tag does not break registration of an otherwise valid tool.
        """
        ops: list[STLOperation] = []
        for token in data.get("operation_types", []):
            op = operation_from_token(str(token))
            if op is None:
                logger.warning(
                    "Capability %r declares unknown operation_type %r — skipped",
                    data.get("capability_id"), token,
                )
                continue
            if op not in ops:
                ops.append(op)

        raw_kind = data.get("kind", "tool")
        try:
            kind = CapabilityKind(raw_kind)
        except ValueError:
            logger.warning("Unknown capability kind %r — defaulting to tool", raw_kind)
            kind = CapabilityKind.TOOL

        return cls(
            capability_id=str(data["capability_id"]),
            kind=kind,
            version=str(data.get("version", "1.0.0")),
            operation_types=ops,
            input_schema=dict(data.get("input_schema", {})),
            output_schema=dict(data.get("output_schema", {})),
            produces_facts=bool(data.get("produces_facts", True)),
            cost_profile=CostProfile.from_dict(data.get("cost_profile", {})),
            serves_intents=list(data.get("serves_intents", [])),
            consumes_facts=list(data.get("consumes_facts", [])),
            dependencies=list(data.get("dependencies", [])),
            mutually_exclusive_with=list(data.get("mutually_exclusive_with", [])),
            data_residency=str(data.get("data_residency", "")),
            allowed_policy_domains=list(data.get("allowed_policy_domains", [])),
            embedding_vector=(
                list(data["embedding_vector"]) if data.get("embedding_vector") else None
            ),
            embedding_model=str(data.get("embedding_model", "")),
            metadata=dict(data.get("metadata", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        """Render the descriptor as its canonical JSON form."""
        out: dict[str, Any] = {
            "capability_id": self.capability_id,
            "kind": self.kind.value,
            "version": self.version,
            "operation_types": [operation_to_token(op) for op in self.operation_types],
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
            "produces_facts": self.produces_facts,
            "cost_profile": self.cost_profile.to_dict(),
        }
        if self.serves_intents:
            out["serves_intents"] = self.serves_intents
        if self.consumes_facts:
            out["consumes_facts"] = self.consumes_facts
        if self.dependencies:
            out["dependencies"] = self.dependencies
        if self.mutually_exclusive_with:
            out["mutually_exclusive_with"] = self.mutually_exclusive_with
        if self.data_residency:
            out["data_residency"] = self.data_residency
        if self.allowed_policy_domains:
            out["allowed_policy_domains"] = self.allowed_policy_domains
        if self.embedding_vector is not None:
            out["embedding_vector"] = self.embedding_vector
        if self.embedding_model:
            out["embedding_model"] = self.embedding_model
        if self.metadata:
            out["metadata"] = self.metadata
        return out

    # ------------------------------------------------------------------ validate

    def validate(self) -> list[str]:
        """Return a list of validation errors (empty list ⇒ valid).

        Mirrors the required fields of ``schemas/capability-descriptor.json`` so
        callers can validate without a JSON-Schema dependency in the core.
        """
        errors: list[str] = []
        if not self.capability_id:
            errors.append("capability_id is required and must be non-empty")
        if not isinstance(self.kind, CapabilityKind):
            errors.append("kind must be a CapabilityKind")
        if not self.version:
            errors.append("version is required")
        if not self.operation_types:
            errors.append("operation_types must list at least one operation")
        if not isinstance(self.input_schema, dict):
            errors.append("input_schema must be a JSON-Schema object")
        if not isinstance(self.output_schema, dict):
            errors.append("output_schema must be a JSON-Schema object")
        if not isinstance(self.cost_profile, CostProfile):
            errors.append("cost_profile must be a CostProfile")
        if self.embedding_vector is not None and not all(
            isinstance(x, (int, float)) for x in self.embedding_vector
        ):
            errors.append("embedding_vector must contain only numbers")
        return errors
