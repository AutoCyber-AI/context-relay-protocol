# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Contextual Knowledge Fabric — 4-mode retrieval, community detection, pub/sub."""

from .cdgr import CDGRConnector, CDGRResult, cdgr_expand, cdr_cdgr_pipeline
from .community import Community, CommunityDetector, CommunityResult
from .fabric import CKFConfig, CKFHealth, ContextualKnowledgeFabric
from .gc import GarbageCollector, GCResult
from .graph_edges import (
    CKFEdge,
    EdgeType,
    GraphEdgeStore,
    build_edges,
    build_edges_from_hnsw,
    get_neighbours,
)
from .graph_walk import GraphWalkResult, graph_walk
from .merge import MergedFact, MergeResult, multi_mode_merge
from .pattern_query import PatternQueryResult, pattern_query
from .pubsub import CKFEvent, CKFEventType, PubSubEventBus
from .semantic import SemanticResult, semantic_fallback
from .vector_index import VectorIndex, active_embedding_model_id, encode_texts

__all__ = [
    "CKFConfig",
    "CKFEdge",
    "CKFEvent",
    "CKFEventType",
    "CKFHealth",
    "CDGRConnector",
    "CDGRResult",
    "Community",
    "CommunityDetector",
    "CommunityResult",
    "ContextualKnowledgeFabric",
    "EdgeType",
    "GCResult",
    "GarbageCollector",
    "GraphEdgeStore",
    "GraphWalkResult",
    "MergeResult",
    "MergedFact",
    "PatternQueryResult",
    "PubSubEventBus",
    "SemanticResult",
    "VectorIndex",
    "active_embedding_model_id",
    "build_edges",
    "build_edges_from_hnsw",
    "cdr_cdgr_pipeline",
    "cdgr_expand",
    "encode_texts",
    "get_neighbours",
    "graph_walk",
    "multi_mode_merge",
    "pattern_query",
    "semantic_fallback",
]

