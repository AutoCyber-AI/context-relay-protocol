# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Core protocol — orchestrator, task intent, windows, sessions, config, errors."""

from crp.core.batch import BatchResult, dispatch_batch, ingest_batch
from crp.core.config import ConfigurationResolver, CRPConfig
from crp.core.errors import (
    BudgetExhaustedError,
    CRPError,
    ProviderError,
    SessionClosedError,
    SessionExpiredError,
)
from crp.core.idempotency import CachedResult, RequestDeduplicator, SessionLock
from crp.core.orchestrator import (
    CRPOrchestrator,
    ExtractionResult,
    StreamEvent,
)
from crp.core.session import (
    CostEstimate,
    EnvelopePreview,
    QualityReport,
    RemainingBudget,
    SecurityFlags,
    SessionHandle,
    SessionStatus,
)
from crp.core.task_intent import TaskIntent
from crp.core.window import (
    TransferType,
    WindowDAG,
    WindowEdge,
    WindowMetrics,
    WindowNode,
    WindowPattern,
    WindowState,
    partition_fan_in_budget,
    select_transfer_type,
)

__all__ = [
    # Orchestrator
    "CRPOrchestrator",
    "ExtractionResult",
    "StreamEvent",
    # Config
    "ConfigurationResolver",
    "CRPConfig",
    # Session
    "SessionHandle",
    "SessionStatus",
    "CostEstimate",
    "EnvelopePreview",
    "QualityReport",
    "RemainingBudget",
    "SecurityFlags",
    # Task
    "TaskIntent",
    # Window
    "WindowDAG",
    "WindowEdge",
    "WindowMetrics",
    "WindowNode",
    "WindowPattern",
    "WindowState",
    "TransferType",
    "select_transfer_type",
    "partition_fan_in_budget",
    # Errors
    "CRPError",
    "BudgetExhaustedError",
    "ProviderError",
    "SessionClosedError",
    "SessionExpiredError",
    # Batch
    "BatchResult",
    "dispatch_batch",
    "ingest_batch",
    # Idempotency
    "CachedResult",
    "RequestDeduplicator",
    "SessionLock",
]
