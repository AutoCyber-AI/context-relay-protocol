# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""State management — facts, warm store, event log, snapshots, cold storage."""

from .cold_storage import PersistedStateHeader, persist_to_cold, restore_from_cold
from .compaction import CompactionConfig, CompactionResult, compact, should_compact  # noqa: F401
from .critical_state import CriticalState, StructuralState
from .event_log import FactEventLog
from .fact import StateFact, set_embedding_function
from .serialization import FactGraphSerializer
from .snapshot import EventLogSnapshot, SnapshotManager
from .backends import InMemoryBackend, StorageBackend, StorageBackendError
from .warm_store import WarmStateStore, WarmStoreConfig
from .coverage_set import CoverageEntry, CoverageSet, ResidualItem
from .cso import (
    CognitiveStateObject,
    Decision,
    DependencyEdge,
    EstablishedFact,
    GoalMode,
    GoalState,
    ProvenanceKind,
    extract_cso,
    preservation_report,
    relay_cso,
)
from .horizons import ContextTier, MultiHorizonContext, TurnEntry
from .memory_authority import (
    Authority,
    MemoryAuditEvent,
    MemoryAuthorityLattice,
    MemoryEntry,
    MemoryOperation,
    MemoryTier,
)
from .scratch_buffer import ScratchBuffer, ScratchEntry, ScratchPersistence
from .storage import StorageRouter, AccessPattern, RollingContextLog, HotCache, InvertedIndex, EphemeralStore

__all__ = [
    "AccessPattern",
    "CognitiveStateObject",
    "CoverageEntry",
    "CoverageSet",
    "CriticalState",
    "CompactionConfig",
    "CompactionResult",
    "compact",
    "Decision",
    "DependencyEdge",
    "EphemeralStore",
    "EstablishedFact",
    "EventLogSnapshot",
    "FactEventLog",
    "FactGraphSerializer",
    "GoalMode",
    "GoalState",
    "HotCache",
    "InvertedIndex",
    "ProvenanceKind",
    "ResidualItem",
    "RollingContextLog",
    "SnapshotManager",
    "StateFact",
    "StorageRouter",
    "StructuralState",
    "WarmStateStore",
    "WarmStoreConfig",
    "PersistedStateHeader",
    "persist_to_cold",
    "preserve_report",
    "relay_cso",
    "extract_cso",
    "preservation_report",
    "restore_from_cold",
    "set_embedding_function",
    # Storage backends (SPEC-038)
    "InMemoryBackend",
    "StorageBackend",
    "StorageBackendError",
    # Memory authority lattice (SPEC-045)
    "Authority",
    "MemoryAuditEvent",
    "MemoryAuthorityLattice",
    "MemoryEntry",
    "MemoryOperation",
    "MemoryTier",
    # Multi-horizon context (SPEC-028)
    "ContextTier",
    "MultiHorizonContext",
    "TurnEntry",
    # Scratch buffer (SPEC-029)
    "ScratchBuffer",
    "ScratchEntry",
    "ScratchPersistence",
]

