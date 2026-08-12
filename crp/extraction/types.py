# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Extraction pipeline data types — Fact, FactEdge, FactGraph, ExtractionResult.

These dataclasses form the shared data model produced by the 6-stage
graduated extraction pipeline and consumed by the warm store, CKF, and
envelope builder.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from crp.core.context_source import ContextSource


class ContentType(str, Enum):
    """Content complexity classification used to route extraction stages."""

    ENTITY_RICH = "ENTITY_RICH"
    """Text rich in named entities; favours regex/GLiNER stages."""
    REASONING_DENSE = "REASONING_DENSE"
    """Text with arguments, causality, and discourse structure."""
    NARRATIVE = "NARRATIVE"
    """General prose; default routing."""


class RelationType(str, Enum):
    """Semantic relation types stored on ``FactEdge`` records."""

    CONDITION_FOR = "CONDITION_FOR"
    CAUSE_EFFECT = "CAUSE_EFFECT"
    CONTRAST = "CONTRAST"
    CONCESSION = "CONCESSION"
    CONSEQUENCE = "CONSEQUENCE"
    ELABORATION = "ELABORATION"
    SEQUENCE = "SEQUENCE"
    RELATED = "RELATED"


@dataclass
class Fact:
    """Single extracted fact produced by the extraction pipeline.

    Lightweight record — embeddings are typically computed lazily in the state
    layer when facts are added to the warm store or CKF.

    Attributes:
        id: Unique fact identifier.
        text: Normalised fact text.
        category: Semantic category (e.g. "entity", "noun_phrase", "relation").
        source_window_id: Window that produced this fact.
        confidence: Extraction confidence in [0, 1].
        extraction_stage: Pipeline stage that produced this fact (1-6).
        created_at: Unix timestamp of extraction.
        metadata: Arbitrary structured metadata.
        source: Context-source provenance (CRP 2.1+, §7.14.3).
        flagged_confidence: True if confidence failed quality gate.
        confidence_flag_reason: Reason for confidence flag.
        superseded_by: ID of the fact that superseded this one.
        supersession_confidence: Confidence of the supersession decision.
    """

    # Metadata size limits (§audit M4)
    MAX_METADATA_KEYS: int = 64
    MAX_KEY_LENGTH: int = 128
    MAX_VALUE_SIZE: int = 4096

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    text: str = ""
    category: str = ""
    source_window_id: str = ""
    confidence: float = 0.0
    extraction_stage: int = 0
    created_at: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    # Context-source provenance (CRP 2.1, §7.14.3). Optional — ``None``
    # preserves v2.0 behaviour. Populated by dispatch-router message
    # assembly when the upstream source is known, or by the detective-mode
    # parser (:func:`crp.core.context_source.detect_source_kind`) as a
    # heuristic fallback. Consumed by the envelope builder's
    # ``[CONTEXT_SOURCES]`` section and by ``crp-comply`` deliverables.
    source: ContextSource | None = None

    # Quality gate flags (set by post-extraction validation)
    flagged_confidence: bool = False
    confidence_flag_reason: str = ""

    # Supersession (set by contradiction detection)
    superseded_by: str | None = None
    supersession_confidence: float = 0.0

    def validate_metadata(self) -> None:
        """Enforce metadata size limits (§audit M4).

        Raises:
            ValueError: If metadata exceeds configured key/value/count bounds.
        """
        if len(self.metadata) > self.MAX_METADATA_KEYS:
            raise ValueError(
                f"Fact metadata exceeds {self.MAX_METADATA_KEYS} keys "
                f"(got {len(self.metadata)})"
            )
        for key, value in self.metadata.items():
            if len(str(key)) > self.MAX_KEY_LENGTH:
                raise ValueError(
                    f"Metadata key exceeds {self.MAX_KEY_LENGTH} chars: {str(key)[:50]}..."
                )
            val_str = str(value)
            if len(val_str) > self.MAX_VALUE_SIZE:
                raise ValueError(
                    f"Metadata value for '{key}' exceeds {self.MAX_VALUE_SIZE} chars "
                    f"(got {len(val_str)})"
                )

    def set_metadata(self, key: str, value: Any) -> None:
        """Set a metadata key with size validation.

        Args:
            key: Metadata key.
            value: Metadata value.

        Raises:
            ValueError: If the key or value exceeds configured size limits.
        """
        if len(str(key)) > self.MAX_KEY_LENGTH:
            raise ValueError(f"Metadata key exceeds {self.MAX_KEY_LENGTH} chars")
        if len(str(value)) > self.MAX_VALUE_SIZE:
            raise ValueError(f"Metadata value exceeds {self.MAX_VALUE_SIZE} chars")
        if key not in self.metadata and len(self.metadata) >= self.MAX_METADATA_KEYS:
            raise ValueError(f"Metadata exceeds {self.MAX_METADATA_KEYS} keys limit")
        self.metadata[key] = value


@dataclass
class FactEdge:
    """Directed relation between two facts or text spans.

    Attributes:
        id: Unique edge identifier.
        source_id: ID of the source fact.
        target_id: ID of the target fact.
        relation_type: Semantic relation type.
        confidence: Relation confidence in [0, 1].
        source_stage: Pipeline stage that produced this edge.
        metadata: Arbitrary structured metadata.
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source_id: str = ""
    target_id: str = ""
    relation_type: RelationType | str = RelationType.RELATED
    confidence: float = 0.0
    source_stage: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class FactGraph:
    """In-memory graph of facts and edges.

    Maintains adjacency indices for O(1) edge lookup (§audit L4).

    Attributes:
        nodes: Mapping from fact ID to ``Fact``.
        edges: List of all edges in the graph.
        _edges_from: Index of outgoing edges by source fact ID.
        _edges_to: Index of incoming edges by target fact ID.
    """

    nodes: dict[str, Fact] = field(default_factory=dict)
    edges: list[FactEdge] = field(default_factory=list)
    # Edge indices for O(1) lookup (§audit L4)
    _edges_from: dict[str, list[FactEdge]] = field(default_factory=lambda: {})
    _edges_to: dict[str, list[FactEdge]] = field(default_factory=lambda: {})

    def add_fact(self, fact: Fact) -> None:
        """Add or update a fact node."""
        self.nodes[fact.id] = fact

    def remove_fact(self, fact_id: str) -> None:
        """Remove a fact and all its edges from the graph (§audit2 STATE-H5).

        Args:
            fact_id: ID of the fact to remove.
        """
        self.nodes.pop(fact_id, None)
        # Remove edges referencing this fact
        self.edges = [e for e in self.edges
                      if e.source_id != fact_id and e.target_id != fact_id]
        # Clean edge indices
        self._edges_from.pop(fact_id, None)
        self._edges_to.pop(fact_id, None)
        # Remove from other nodes' index entries
        for idx in (self._edges_from, self._edges_to):
            for key in list(idx):
                idx[key] = [e for e in idx[key]
                            if e.source_id != fact_id and e.target_id != fact_id]
                if not idx[key]:
                    del idx[key]

    def add_edge(self, edge: FactEdge) -> None:
        """Add an edge if both endpoint facts exist.

        Skips edges referencing non-existent facts (§audit G7) and maintains
        the O(1) adjacency indices.

        Args:
            edge: Edge to add.
        """
        # Skip edges referencing non-existent facts (§audit G7)
        if edge.source_id not in self.nodes or edge.target_id not in self.nodes:
            return
        self.edges.append(edge)
        # Maintain O(1) edge indices (§audit L4)
        self._edges_from.setdefault(edge.source_id, []).append(edge)
        self._edges_to.setdefault(edge.target_id, []).append(edge)

    def edges_from(self, fact_id: str) -> list[FactEdge]:
        """Return outgoing edges from ``fact_id``."""
        return list(self._edges_from.get(fact_id, []))

    def edges_to(self, fact_id: str) -> list[FactEdge]:
        """Return incoming edges to ``fact_id``."""
        return list(self._edges_to.get(fact_id, []))

    def subgraph_for(self, fact_ids: set[str], max_hops: int = 1) -> FactGraph:
        """Return subgraph containing *fact_ids* plus neighbours within *max_hops*.

        Args:
            fact_ids: Seed fact IDs.
            max_hops: Number of graph hops to include around seeds.

        Returns:
            A new ``FactGraph`` containing the induced subgraph.
        """
        visited: set[str] = set(fact_ids)
        frontier = set(fact_ids)
        for _ in range(max_hops):
            next_frontier: set[str] = set()
            for fid in frontier:
                for e in self._edges_from.get(fid, []):
                    if e.target_id not in visited:
                        next_frontier.add(e.target_id)
                for e in self._edges_to.get(fid, []):
                    if e.source_id not in visited:
                        next_frontier.add(e.source_id)
            visited |= next_frontier
            frontier = next_frontier
        sub_nodes = {fid: self.nodes[fid] for fid in visited if fid in self.nodes}
        sub_edges = [e for e in self.edges if e.source_id in visited and e.target_id in visited]
        sub = FactGraph(nodes=sub_nodes, edges=sub_edges)
        # Rebuild edge indices for the subgraph (§audit2 STATE-H4)
        for e in sub_edges:
            sub._edges_from.setdefault(e.source_id, []).append(e)
            sub._edges_to.setdefault(e.target_id, []).append(e)
        return sub

    def serialize_for_envelope(self) -> str:
        """Plain-text serialisation for envelope packing.

        Returns:
            Bulleted list of facts and their outgoing relations.
        """
        lines: list[str] = []
        for fid, fact in self.nodes.items():
            lines.append(f"- {fact.text}")
            for edge in self.edges_from(fid):
                target = self.nodes.get(edge.target_id)
                if target:
                    rel = edge.relation_type
                    if isinstance(rel, RelationType):
                        rel = rel.value
                    lines.append(f"  ↳ [{rel}] {target.text}")
        return "\n".join(lines)


class ValidationSeverity(str, Enum):
    """Severity levels for quality-gate issues."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class ValidationIssue:
    """Single issue found by the quality gate.

    Attributes:
        type: Issue classification.
        severity: Issue severity.
        detail: Human-readable description.
    """

    type: str = ""
    severity: ValidationSeverity = ValidationSeverity.LOW
    detail: str = ""


@dataclass
class ValidationResult:
    """Result from one quality-gate tier.

    Attributes:
        tier: Quality-gate tier number.
        passed: True if the tier passed.
        issues: Issues found at this tier.
    """

    tier: int = 0
    passed: bool = True
    issues: list[ValidationIssue] = field(default_factory=list)


@dataclass
class Contradiction:
    """A detected contradiction between two facts.

    Attributes:
        fact_a: First fact.
        fact_b: Second fact.
        similarity: Semantic similarity between the facts.
        content_diff: Normalised content difference score.
        confidence: Confidence that the pair is contradictory.
    """

    fact_a: Fact | None = None
    fact_b: Fact | None = None
    similarity: float = 0.0
    content_diff: float = 0.0
    confidence: float = 0.0


@dataclass
class FactEvent:
    """Immutable audit-log entry for fact lifecycle events.

    Attributes:
        event_id: Monotonic event identifier.
        timestamp: Unix timestamp of the event.
        window_id: Window that triggered the event.
        event_type: One of "created", "superseded", "compacted",
            "archived", or "restored".
        fact_id: Affected fact ID.
        payload: Additional structured context.
    """

    event_id: int = 0
    timestamp: float = field(default_factory=time.time)
    window_id: str = ""
    event_type: str = ""  # "created" | "superseded" | "compacted" | "archived" | "restored"
    fact_id: str = ""
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExtractionResult:
    """Complete extraction result from the graduated pipeline.

    Attributes:
        extraction_id: Unique extraction run identifier.
        source_window_id: Window that produced this extraction.
        timestamp: Unix timestamp of extraction completion.
        facts: Extracted facts.
        edges: Extracted relations.
        fact_graph: Built graph from facts and edges.
        stages_run: Pipeline stages that executed.
        stages_skipped: Pipeline stages that were skipped.
        total_extraction_latency_ms: Total extraction time.
        per_stage_latency: Latency per stage.
        total_facts: Total number of facts.
        total_edges: Total number of edges.
        average_confidence: Mean fact confidence.
        entity_density: Entities per word.
        relation_density: Edges per fact.
        content_type: Detected content complexity.
        discourse_markers_found: Number of discourse markers found.
        stage_yields: Fact counts per stage.
        escalation_triggers: Reasons stages were escalated.
        quality_gate_passed: Whether the quality gate passed.
        quality_issues: Quality gate issue messages.
        facts_after_normalization: Fact count after normalization.
    """

    extraction_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source_window_id: str = ""
    timestamp: float = field(default_factory=time.time)

    # Extracted data
    facts: list[Fact] = field(default_factory=list)
    edges: list[FactEdge] = field(default_factory=list)
    fact_graph: FactGraph = field(default_factory=FactGraph)

    # Pipeline execution
    stages_run: list[int] = field(default_factory=list)
    stages_skipped: list[int] = field(default_factory=list)
    total_extraction_latency_ms: float = 0.0
    per_stage_latency: dict[int, float] = field(default_factory=dict)

    # Quality metrics
    total_facts: int = 0
    total_edges: int = 0
    average_confidence: float = 0.0
    entity_density: float = 0.0
    relation_density: float = 0.0

    # Content classification
    content_type: ContentType = ContentType.NARRATIVE
    discourse_markers_found: int = 0

    # Pipeline state (for self-calibration)
    stage_yields: dict[int, int] = field(default_factory=dict)
    escalation_triggers: list[str] = field(default_factory=list)

    # Quality gate
    quality_gate_passed: bool = True
    quality_issues: list[str] = field(default_factory=list)

    # Normalization
    facts_after_normalization: int = 0

    @property
    def success(self) -> bool:
        """Return True if the quality gate passed."""
        return self.quality_gate_passed

    def finalize(self) -> None:
        """Compute aggregate metrics and build the fact graph."""
        self.total_facts = len(self.facts)
        self.total_edges = len(self.edges)
        if self.facts:
            self.average_confidence = sum(f.confidence for f in self.facts) / len(self.facts)
        self.relation_density = self.total_edges / max(self.total_facts, 1)
        self.facts_after_normalization = self.total_facts
        # Build graph
        self.fact_graph = FactGraph()
        for f in self.facts:
            self.fact_graph.add_fact(f)
        for e in self.edges:
            self.fact_graph.add_edge(e)
