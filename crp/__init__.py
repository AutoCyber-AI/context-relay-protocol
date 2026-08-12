# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""
CRP — Context Relay Protocol.

Unbounded context · Unbounded generation · Amplified reasoning.

Usage::

    import crp

    client = crp.Client(provider=my_provider)
    result = client.dispatch("You are helpful.", "Explain CRP.")
    print(result.output)
"""

from __future__ import annotations

import os
import sys

# ── Windows OpenMP duplicate-runtime crash mitigation ────────────────────
# On Windows, numpy/scipy/scikit-learn/torch each bundle their own OpenMP
# runtime DLL. When several of them coexist in one process (as they do once
# the optional [nlp]/[full] extras — sentence-transformers, GLiNER, torch —
# are installed alongside numpy/scipy/scikit-learn), loading more than one
# OpenMP runtime can trigger a native access violation (observed as a fatal
# crash inside `torch`'s C extension during model loading, e.g.
# `GLiNER.from_pretrained(...)`). This must be set BEFORE numpy/scipy/torch
# are first imported anywhere in the process, so it lives at the very top of
# this package's __init__, ahead of every other CRP import.
if sys.platform == "win32":
    os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
    os.environ.setdefault("OMP_NUM_THREADS", "1")

from crp._version import __version__
from crp.config import CRPConfig
from crp.core.config import ConfigurationResolver
from crp.core.context_enforcer import (
    AuditSink,
    ContextEnforcer,
    EnforcementPolicy,
    EnforcementResult,
    InjectionSignal,
    InMemoryAuditSink,
    LoggingAuditSink,
    default_enforcer,
    detect_injection_signals,
    observed_content,
    set_default_enforcer,
)
from crp.core.context_source import (
    AttestationMismatch,
    ContextManifest,
    ContextSource,
    ManifestValidationError,
    SourceKind,
    SourceOrigin,
    TrustLevel,
    check_attestation,
    detect_source_kind,
)
from crp.core.errors import (
    BudgetExhaustedError,
    ChainVerificationFailedError,
    CRPError,
    ErrorCode,
    ProviderError,
    ProviderTimeoutError,
    RateLimitExceededError,
    SecurityInvariantError,
    SessionClosedError,
    SessionExpiredError,
    SignatureInvalidError,
    StateCorruptedError,
    ValidationError,
)
from crp.core.ledger_backends import (
    AsyncBufferedSink,
    HTTPForwardingSink,
    JSONLinesFileSink,
    NullSink,
)
from crp.core.manifest_derive import (
    content_hash,
    derive_manifest_from_messages,
    derive_source_from_message,
    derive_sources_from_messages,
)
from crp.core.manifest_ledger import (
    EnvVarKeyProvider,
    KeyProvider,
    LedgerChainError,
    ManifestLedger,
    ManifestLedgerEntry,
    RotatingKeyProvider,
)
from crp.core.orchestrator import CRPOrchestrator, ExtractionResult, StreamEvent
from crp.core.session import (
    CostEstimate,
    QualityReport,
    SessionHandle,
    SessionStatus,
)
from crp.core.task_intent import TaskIntent
from crp.license_guard import _startup_check as _license_startup_check

# ── License guard — advisory IP protection checks (§ELv2) ──
_license_startup_check()

# Convenience alias — spec §9.1 says ``import crp; client = crp.Client(...)``
# NOTE: crp.Client currently aliases CRPOrchestrator for backward compatibility.
# The new progressive SDK client is available as crp.SDKClient (SPEC-032).
Client = CRPOrchestrator

# Lazy imports for advanced types — avoids pulling heavy subsystems on ``import crp``
def __getattr__(name: str):
    _ADVANCED = {
        "CKFConfig": "crp.ckf.fabric",
        "CKFHealth": "crp.ckf.fabric",
        "ContextualKnowledgeFabric": "crp.ckf.fabric",
        "ContinuationConfig": "crp.continuation.manager",
        "ContinuationManager": "crp.continuation.manager",
        "CriticalState": "crp.state.critical_state",
        "StructuralState": "crp.state.critical_state",
        "EnvelopePreview": "crp.core.session",
        "EnvelopeResult": "crp.envelope.builder",
        "EnvelopeState": "crp.envelope.builder",
        "ExtractionPipeline": "crp.extraction.pipeline",
        "Fact": "crp.extraction.types",
        "FactEdge": "crp.extraction.types",
        "FactGraph": "crp.extraction.types",
        "WarmStateStore": "crp.state.warm_store",
        "WarmStoreConfig": "crp.state.warm_store",
        # v4 SDK + safety (lazy-loaded to avoid heavy imports)
        "SDKClient": "crp.sdk.client",
        "CRPClient": "crp.sdk.client",
        "Agent": "crp.agent_sdk.agent",
        "AgentResponse": "crp.agent_sdk.agent",
        "CRPCompletionResponse": "crp.sdk.response",
        "CRPAskResponse": "crp.sdk.response",
        "CRPResponseMeta": "crp.sdk.response",
        "SourceAttribution": "crp.sdk.response",
        "SafetyControlPlane": "crp.security.control_plane",
        "Checkpoint": "crp.security.checkpoint",
        "SafetyManifest": "crp.security.safety_manifest",
        "ApplicationProfile": "crp.core.app_profile",
        "FrameworkKind": "crp.core.app_profile",
        "ProviderKind": "crp.core.app_profile",
        "ContextStrategy": "crp.core.app_profile",
        "ToolInfo": "crp.core.app_profile",
        "build_profile_from_messages": "crp.core.app_profile",
    }
    if name in _ADVANCED:
        import importlib
        mod = importlib.import_module(_ADVANCED[name])
        return getattr(mod, name)
    raise AttributeError(f"module 'crp' has no attribute {name!r}")


__all__ = [
    # Core public API
    "__version__",
    "Client",
    "CRPOrchestrator",
    "CRPConfig",           # Unified config (SPEC-037)
    "ConfigurationResolver",
    "TaskIntent",
    # Context-source provenance (CRP 2.1, §7.14.3)
    "SourceKind",
    "SourceOrigin",
    "TrustLevel",
    "ContextSource",
    "ContextManifest",
    "ManifestValidationError",
    "AttestationMismatch",
    "detect_source_kind",
    "check_attestation",
    # Context enforcement & ledger (CRP 2.2, §7.14.4-5)
    "ContextEnforcer",
    "EnforcementPolicy",
    "EnforcementResult",
    "InjectionSignal",
    "AuditSink",
    "LoggingAuditSink",
    "InMemoryAuditSink",
    "detect_injection_signals",
    "observed_content",
    "default_enforcer",
    "set_default_enforcer",
    "ManifestLedger",
    "ManifestLedgerEntry",
    "LedgerChainError",
    "KeyProvider",
    "EnvVarKeyProvider",
    "RotatingKeyProvider",
    # Ledger forwarding sinks (CRP 2.3, §7.14.5)
    "JSONLinesFileSink",
    "HTTPForwardingSink",
    "AsyncBufferedSink",
    "NullSink",
    # Derived manifests (CRP 2.3, §7.14.6)
    "content_hash",
    "derive_source_from_message",
    "derive_sources_from_messages",
    "derive_manifest_from_messages",
    # Error types (§audit L2)
    "CRPError",
    "ErrorCode",
    "BudgetExhaustedError",
    "ChainVerificationFailedError",
    "ProviderError",
    "ProviderTimeoutError",
    "RateLimitExceededError",
    "SecurityInvariantError",
    "SessionClosedError",
    "SessionExpiredError",
    "SignatureInvalidError",
    "StateCorruptedError",
    "ValidationError",
    # Results
    "QualityReport",
    "CostEstimate",
    "SessionHandle",
    "SessionStatus",
    "SourceAttribution",
    "StreamEvent",
    "ExtractionResult",
    # Advanced (lazy-loaded)
    "CKFConfig",
    "CKFHealth",
    "ContextualKnowledgeFabric",
    "ContinuationConfig",
    "ContinuationManager",
    "CriticalState",
    "EnvelopePreview",
    "EnvelopeResult",
    "EnvelopeState",
    "ExtractionPipeline",
    "Fact",
    "FactEdge",
    "FactGraph",
    "StructuralState",
    "WarmStateStore",
    "WarmStoreConfig",
    # Progressive SDK + Agent SDK (CRPv6)
    "SDKClient",
    "CRPClient",
    "Agent",
    "AgentResponse",
    "CRPCompletionResponse",
    "CRPAskResponse",
    "CRPResponseMeta",
    "SourceAttribution",
]
