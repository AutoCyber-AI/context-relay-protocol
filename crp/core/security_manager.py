# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""SecurityManager — facade for all CRP security subsystems (§audit4 CQ-C1).

Extracts the 18 security & compliance subsystem initializations from
`CRPOrchestrator.__init__()` into a single cohesive class, reducing
orchestrator init from ~360 lines to ~250 lines.

All subsystems remain accessible as attributes on the manager instance.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class SecurityManager:
    """Groups all CRP security and compliance subsystems (§7).

    Subsystems initialized:
    - InputValidator (§7.4) — Layer 1, cannot be disabled
    - InjectionDetector (§7.5) — advisory, never blocks
    - SessionBindingManager (§7.1) — HMAC-SHA256 key derivation
    - RBACEnforcer (§7.10) — role-based access + rate limiting
    - FactIntegrityChain (§7.2, §7.7) — BLAKE3/SHA-256 hash chain
    - StateEncryptor (§7.3) — AES-256-GCM
    - IngestQuarantine (§7.8) — 1-window anti-poisoning
    - EmbeddingDefense (§7.11) — SQ8 + XOR salting
    - PIIScanner (§7.12) — pattern-based PII detection
    - RetentionManager (§7.12) — auto-expiry per classification
    - ErasureManager (§7.12) — GDPR Art. 17 right to erasure
    - DataLineageTracker (§7.12) — provenance tracking
    - ConsentManager (§7.13) — purpose-based consent
    - ProcessingRecordKeeper (§7.13) — GDPR Art. 30 records
    - HumanOversightController (§7.13) — EU AI Act Art. 14
    - ComplianceAuditTrail (§7.14) — tamper-evident HMAC chain
    - RiskClassifier (§7.15) — EU AI Act risk classification
    - ComplianceReporter (§7.15) — regulatory reporting
    """

    def __init__(
        self,
        session_id: str,
        session_key: bytes,
        config: Any,
    ) -> None:
        from crp.security.audit_trail import ComplianceAuditTrail
        from crp.security.binding import SessionBindingManager
        from crp.security.compliance import ComplianceReporter, RiskClassifier
        from crp.security.consent import (
            ConsentManager,
            HumanOversightController,
            ProcessingRecordKeeper,
        )
        from crp.security.embedding_defense import EmbeddingDefense
        from crp.security.encryption import StateEncryptor
        from crp.security.injection import InjectionDetector
        from crp.security.integrity import FactIntegrityChain
        from crp.security.privacy import (
            DataLineageTracker,
            ErasureManager,
            PIIScanner,
            RetentionManager,
        )
        from crp.security.quarantine import IngestQuarantine
        from crp.security.rbac import RBACEnforcer, RateLimitConfig, Role
        from crp.security.validation import InputValidator

        # Layer 1 — input validation (§7.4)
        self.input_validator = InputValidator()

        # Injection detection — advisory, never blocks (§7.5)
        self.injection_detector = InjectionDetector()

        # Session binding — HMAC-SHA256 key derivation (§7.1)
        binding_secret = config.get("binding_secret", "")
        secret_bytes = binding_secret.encode("utf-8") if binding_secret else None
        self.session_binding = SessionBindingManager(master_secret=secret_bytes)
        self.session_binding.create_session(session_id)

        # RBAC — role-based access control + rate limiting (§7.10)
        default_role_name = config.get("default_role", "OPERATOR")
        try:
            default_role = Role[default_role_name.upper()]
        except KeyError:
            default_role = Role.OPERATOR
        rate_config = RateLimitConfig(
            dispatch_per_minute=config.max_dispatch_rate,
        )
        self.rbac = RBACEnforcer(role=default_role, config=rate_config)

        # Fact integrity chain — BLAKE3/SHA-256 hash chain (§7.2, §7.7)
        self.integrity_chain = FactIntegrityChain(
            session_key=self.session_binding.session_key,
        )

        # State encryption — AES-256-GCM (§7.3)
        self.encryptor = StateEncryptor(self.session_binding.session_key)

        # Ingest quarantine — 1-window anti-poisoning (§7.8)
        self.quarantine = IngestQuarantine()

        # Embedding defense — SQ8 + XOR salting (§7.11)
        self.embedding_defense = EmbeddingDefense()

        # PII scanner — pattern-based detection, advisory (§7.12)
        self.pii_scanner = PIIScanner()

        # Retention manager — auto-expiry per classification level (§7.12)
        self.retention_manager = RetentionManager()

        # Erasure manager — GDPR Art. 17 right to erasure (§7.12)
        self.erasure_manager = ErasureManager()

        # Data lineage tracker — provenance tracking (§7.12)
        self.lineage_tracker = DataLineageTracker()

        # Consent manager — purpose-based consent (§7.13)
        self.consent_manager = ConsentManager(session_id=session_id)

        # Processing record keeper — GDPR Art. 30 records (§7.13)
        self.processing_records = ProcessingRecordKeeper(session_id=session_id)

        # Human oversight controller — EU AI Act Art. 14 (§7.13)
        self.human_oversight = HumanOversightController()

        # Compliance audit trail — tamper-evident HMAC chain (§7.14)
        self.compliance_audit = ComplianceAuditTrail(session_id=session_id)

        # Risk classifier + compliance reporter (§7.15)
        self.risk_classifier = RiskClassifier()
        self.compliance_reporter = ComplianceReporter()

    @property
    def session_key(self) -> bytes:
        """Return the session binding key for use by other subsystems."""
        return self.session_binding.session_key
