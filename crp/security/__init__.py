# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Security layer — defense-in-depth for the CRP SDK (§07).

Modules:
    binding      — Session binding (HMAC-SHA256 key derivation)
    integrity    — Fact integrity chain (BLAKE3 hash + HMAC)
    encryption   — Encryption at rest (AES-256-GCM)
    validation   — Input validation (Layer 1, cannot disable)
    injection    — Injection detection (Layer 2, advisory only)
    quarantine   — Anti-poisoning (1-window quarantine)
    rbac         — RBAC + rate limiting
    embedding_defense — SQ8 quantization + XOR salting
    privacy      — Data classification, PII detection, retention, erasure (§7.12)
    consent      — Consent management, processing records, human oversight (§7.13)
    audit_trail  — Tamper-evident HMAC-signed compliance audit trail (§7.14)
    compliance   — EU AI Act + ISO 42001 compliance framework (§7.15)
"""

from .audit_trail import ComplianceAuditTrail, ComplianceEventType
from .binding import SessionBindingManager
from .checkpoint import (
    Checkpoint,
    CheckpointRejectAction,
    CheckpointResolution,
    CheckpointResolutionAction,
    CheckpointTimeoutAction,
    CheckpointTrigger,
)
from .clarify import (
    ClarificationAction,
    ClarificationHandler,
    ClarificationRequest,
    ClarificationResolution,
    resolve_clarification,
)
from .compliance import (
    AIRiskLevel,
    AISystemCategory,
    ComplianceReporter,
    RiskAssessment,
    RiskClassifier,
    TransparencyDeclaration,
)
from .consent import (
    ConsentManager,
    HumanOversightController,
    HumanOversightLevel,
    ProcessingPurpose,
    ProcessingRecordKeeper,
)
from .embedding_defense import EmbeddingDefense, ProtectedEmbedding
from .encryption import EncryptedBlob, StateEncryptor
from .injection import InjectionDetector, InjectionReport, InjectionType
from .integrity import FactIntegrityChain, compute_fact_hash
from .privacy import (
    DataClassification,
    DataLineageTracker,
    ErasureManager,
    PIIScanner,
    RetentionManager,
)
from .quarantine import IngestQuarantine, QuarantineReport
from .rbac import Permission, RateLimitConfig, RBACEnforcer, Role
from .session_token import (
    DEFAULT_TOKEN_LIFETIME,
    SessionTokenPayload,
    TokenStatus,
    TokenValidation,
    build_token,
    derive_signing_key,
    format_set_session_header,
    issue_token,
    parse_token,
    validate_token,
)
from .control_plane import CustomSafetyRule, SafetyControlPlane, get_default_control_plane
from .coverage import SafetyCapability, SafetyCoverageMap
from .safety_manifest import SafetyManifest
from .kill_switch import KillIncident, KillSwitch, KillSwitchReason, KillSwitchState
from .trust_monitor import (
    IndicatorOfCompromise,
    TrustAction,
    TrustActions,
    TrustDecision,
    TrustMonitor,
    TrustMonitorConfig,
)
from .validation import InputValidator, ValidationResult

__all__ = [
    # Compliance (§7.15)
    "AIRiskLevel",
    "AISystemCategory",
    "ComplianceAuditTrail",
    "ComplianceEventType",
    "ComplianceReporter",
    # Consent (§7.13)
    "ConsentManager",
    # Privacy (§7.12)
    "DataClassification",
    "DataLineageTracker",
    # Existing
    "EmbeddingDefense",
    "EncryptedBlob",
    "ErasureManager",
    "FactIntegrityChain",
    "HumanOversightController",
    "HumanOversightLevel",
    "InjectionDetector",
    "InjectionReport",
    "InjectionType",
    "IngestQuarantine",
    "InputValidator",
    "PIIScanner",
    "Permission",
    "ProcessingPurpose",
    "ProcessingRecordKeeper",
    "ProtectedEmbedding",
    "QuarantineReport",
    "RBACEnforcer",
    "RateLimitConfig",
    "RetentionManager",
    "RiskAssessment",
    "RiskClassifier",
    "Role",
    "SessionBindingManager",
    "StateEncryptor",
    "TransparencyDeclaration",
    "ValidationResult",
    "compute_fact_hash",
    # Safety Control Plane (SPEC-033)
    "Checkpoint",
    "CheckpointRejectAction",
    "CheckpointResolution",
    "CheckpointResolutionAction",
    "CheckpointTimeoutAction",
    "CheckpointTrigger",
    # Clarification bridge (CLARIFY ↔ human-in-the-loop)
    "ClarificationAction",
    "ClarificationHandler",
    "ClarificationRequest",
    "ClarificationResolution",
    "resolve_clarification",
    "CustomSafetyRule",
    "SafetyCapability",
    "SafetyControlPlane",
    "SafetyCoverageMap",
    "SafetyManifest",
    "get_default_control_plane",
    # Kill-switch + trust monitor (SPEC-033 §3.4–3.5)
    "KillIncident",
    "KillSwitch",
    "KillSwitchReason",
    "KillSwitchState",
    "IndicatorOfCompromise",
    "TrustAction",
    "TrustActions",
    "TrustDecision",
    "TrustMonitor",
    "TrustMonitorConfig",
    # Session token v3 (SPEC-007)
    "SessionTokenPayload",
    "TokenStatus",
    "TokenValidation",
    "build_token",
    "issue_token",
    "validate_token",
    "parse_token",
    "derive_signing_key",
    "format_set_session_header",
    "DEFAULT_TOKEN_LIFETIME",
]
