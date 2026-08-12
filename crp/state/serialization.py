# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""FactGraph serialization — on-disk format with schema versioning (§22).

Provides forward/backward compatible serialization of the full fact graph
including nodes, edges, and metadata.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from crp.extraction.types import Fact, FactEdge, FactGraph, RelationType

# ---------------------------------------------------------------------------
# Schema version
# ---------------------------------------------------------------------------

GRAPH_SCHEMA_VERSION = 1


@dataclass
class GraphSerializationHeader:
    """Header for serialized FactGraph files."""

    schema_version: int = GRAPH_SCHEMA_VERSION
    node_count: int = 0
    edge_count: int = 0
    checksum: str = ""


# ---------------------------------------------------------------------------
# FactGraphSerializer
# ---------------------------------------------------------------------------


class FactGraphSerializer:
    """Serialize/deserialize FactGraph to/from disk (§22).

    Format: JSON with header + nodes + edges.
    Schema-versioned for forward/backward compatibility.
    """

    @staticmethod
    def serialize(graph: FactGraph) -> dict[str, Any]:
        """Serialize a FactGraph to a dict."""
        nodes = []
        for _fid, fact in graph.nodes.items():
            nodes.append({
                "id": fact.id,
                "text": fact.text,
                "category": fact.category,
                "source_window_id": fact.source_window_id,
                "confidence": fact.confidence,
                "extraction_stage": fact.extraction_stage,
                "created_at": fact.created_at,
                "superseded_by": fact.superseded_by,
                "supersession_confidence": fact.supersession_confidence,
                "metadata": fact.metadata,
            })

        edges = []
        for edge in graph.edges:
            rel_type = edge.relation_type
            if isinstance(rel_type, RelationType):
                rel_type = rel_type.value
            edges.append({
                "id": edge.id,
                "source_id": edge.source_id,
                "target_id": edge.target_id,
                "relation_type": str(rel_type),
                "confidence": edge.confidence,
                "source_stage": edge.source_stage,
                "metadata": edge.metadata,
            })

        payload = {"nodes": nodes, "edges": edges}
        payload_str = json.dumps(payload, sort_keys=True, default=str)

        try:
            import blake3  # type: ignore[import-untyped]

            checksum = blake3.blake3(payload_str.encode()).hexdigest()
        except ImportError:
            checksum = hashlib.sha256(payload_str.encode()).hexdigest()

        header = GraphSerializationHeader(
            node_count=len(nodes),
            edge_count=len(edges),
            checksum=checksum,
        )

        return {
            "header": {
                "schema_version": header.schema_version,
                "node_count": header.node_count,
                "edge_count": header.edge_count,
                "checksum": header.checksum,
            },
            "nodes": nodes,
            "edges": edges,
        }

    @staticmethod
    def deserialize(data: dict[str, Any]) -> tuple[FactGraph, list[str]]:
        """Deserialize a dict into a FactGraph.  Returns (graph, warnings)."""
        warnings: list[str] = []
        header = data.get("header", {})

        # Schema version check
        version = header.get("schema_version", 0)
        if version != GRAPH_SCHEMA_VERSION:
            warnings.append(f"Schema version mismatch: {version} vs {GRAPH_SCHEMA_VERSION}")

        graph = FactGraph()

        # Deserialize nodes
        for ndata in data.get("nodes", []):
            fact = Fact(
                id=ndata.get("id", ""),
                text=ndata.get("text", ""),
                category=ndata.get("category", ""),
                source_window_id=ndata.get("source_window_id", ""),
                confidence=ndata.get("confidence", 0.0),
                extraction_stage=ndata.get("extraction_stage", 0),
                created_at=ndata.get("created_at", 0.0),
                superseded_by=ndata.get("superseded_by"),
                supersession_confidence=ndata.get("supersession_confidence", 0.0),
                metadata=ndata.get("metadata", {}),
            )
            graph.add_fact(fact)

        # Deserialize edges (check orphans before add_edge, which silently drops them)
        node_ids = set(graph.nodes.keys())
        for edata in data.get("edges", []):
            rel_str = edata.get("relation_type", "RELATED")
            try:
                rel_type: RelationType | str = RelationType(rel_str)
            except ValueError:
                rel_type = rel_str

            edge = FactEdge(
                id=edata.get("id", ""),
                source_id=edata.get("source_id", ""),
                target_id=edata.get("target_id", ""),
                relation_type=rel_type,
                confidence=edata.get("confidence", 0.0),
                source_stage=edata.get("source_stage", 0),
                metadata=edata.get("metadata", {}),
            )
            if edge.source_id not in node_ids:
                warnings.append(f"Orphaned edge source: {edge.source_id}")
            if edge.target_id not in node_ids:
                warnings.append(f"Orphaned edge target: {edge.target_id}")
            graph.add_edge(edge)

        # Verify counts
        expected_nodes = header.get("node_count", 0)
        expected_edges = header.get("edge_count", 0)
        if expected_nodes and len(graph.nodes) != expected_nodes:
            warnings.append(f"Node count mismatch: header={expected_nodes}, loaded={len(graph.nodes)}")
        if expected_edges and len(graph.edges) != expected_edges:
            warnings.append(f"Edge count mismatch: header={expected_edges}, loaded={len(graph.edges)}")

        return graph, warnings

    @classmethod
    def save_to_file(cls, graph: FactGraph, path: str | Path) -> None:
        """Serialize and write to file."""
        data = cls.serialize(graph)
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(data, default=str), encoding="utf-8")

    @classmethod
    def load_from_file(cls, path: str | Path) -> tuple[FactGraph, list[str]]:
        """Load from file.  Returns (graph, warnings)."""
        p = Path(path)
        if not p.exists():
            return FactGraph(), [f"File not found: {path}"]
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            return FactGraph(), [f"Failed to read file: {exc}"]
        return cls.deserialize(data)
