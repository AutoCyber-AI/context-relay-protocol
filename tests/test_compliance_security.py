# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Tests for privacy, consent, audit trail, and compliance modules (§7.12–§7.15)."""

from __future__ import annotations

import time

import pytest

# ---------------------------------------------------------------------------
# §7.12 — Privacy module tests
# ---------------------------------------------------------------------------


class TestDataClassification:
    def test_ordering(self):
        from crp.security.privacy import DataClassification

        assert DataClassification.PUBLIC < DataClassification.INTERNAL
        assert DataClassification.INTERNAL < DataClassification.CONFIDENTIAL
        assert DataClassification.CONFIDENTIAL < DataClassification.RESTRICTED
        assert DataClassification.RESTRICTED < DataClassification.CRITICAL

    def test_values(self):
        from crp.security.privacy import DataClassification

        assert DataClassification.PUBLIC == 0
        assert DataClassification.CRITICAL == 4


class TestPIIScanner:
    def test_detects_email(self):
        from crp.security.privacy import PIIScanner

        scanner = PIIScanner()
        result = scanner.scan("contact us at user@example.com for info")
        assert result.has_pii
        assert "email" in result.pii_types_found

    def test_detects_phone(self):
        from crp.security.privacy import PIIScanner

        scanner = PIIScanner()
        result = scanner.scan("call me at +1-555-123-4567")
        assert result.has_pii
        assert "phone_international" in result.pii_types_found

    def test_detects_credit_card(self):
        from crp.security.privacy import PIIScanner

        scanner = PIIScanner()
        result = scanner.scan("card number is 4111111111111111")
        assert result.has_pii
        assert "credit_card" in result.pii_types_found

    def test_detects_ssn(self):
        from crp.security.privacy import PIIScanner

        scanner = PIIScanner()
        result = scanner.scan("SSN: 123-45-6789")
        assert result.has_pii
        assert "ssn_us" in result.pii_types_found

    def test_detects_ip_address(self):
        from crp.security.privacy import PIIScanner

        scanner = PIIScanner()
        result = scanner.scan("server at 192.168.1.100")
        assert result.has_pii
        assert "ip_address" in result.pii_types_found

    def test_no_pii_clean_text(self):
        from crp.security.privacy import PIIScanner

        scanner = PIIScanner()
        result = scanner.scan("The sky is blue and grass is green.")
        assert not result.has_pii
        assert result.pii_types_found == set()

    def test_hashes_pii_never_stores_raw(self):
        from crp.security.privacy import PIIScanner

        scanner = PIIScanner()
        result = scanner.scan("email is user@example.com")
        for detection in result.detections:
            # text_hash must be a hash, not raw PII
            assert detection.text_hash
            assert "user@example.com" not in detection.text_hash

    def test_highest_classification(self):
        from crp.security.privacy import DataClassification, PIIScanner

        scanner = PIIScanner()
        result = scanner.scan("email: a@b.com and SSN: 123-45-6789")
        assert result.highest_classification >= DataClassification.RESTRICTED

    def test_disabled_types(self):
        from crp.security.privacy import PIIScanner

        scanner = PIIScanner(disabled_types={"email"})
        result = scanner.scan("contact user@example.com")
        assert "email" not in result.pii_types_found

    def test_scan_result_to_dict(self):
        from crp.security.privacy import PIIScanner

        scanner = PIIScanner()
        result = scanner.scan("email: test@test.com")
        d = result.to_dict()
        assert "has_pii" in d
        assert "pii_types" in d

    def test_empty_text(self):
        from crp.security.privacy import PIIScanner

        scanner = PIIScanner()
        result = scanner.scan("")
        assert not result.has_pii


class TestRetentionManager:
    def test_register_and_track(self):
        from crp.security.privacy import DataClassification, RetentionManager

        mgr = RetentionManager()
        record = mgr.register("fact-1", DataClassification.INTERNAL)
        assert record.data_id == "fact-1"
        assert record.classification == DataClassification.INTERNAL
        assert mgr.tracked_count == 1
        assert mgr.active_count == 1

    def test_get_expired(self):
        from crp.security.privacy import (
            DataClassification,
            RetentionManager,
            RetentionPolicy,
        )

        # Set a very short retention
        policy = RetentionPolicy(default_retention_hours=0.0)
        mgr = RetentionManager(policy=policy)
        record = mgr.register("fact-1", DataClassification.INTERNAL)
        # Force expiry
        record.expires_at = time.time() - 1
        expired = mgr.get_expired()
        assert "fact-1" in expired

    def test_mark_purged(self):
        from crp.security.privacy import DataClassification, RetentionManager

        mgr = RetentionManager()
        mgr.register("fact-1", DataClassification.PUBLIC)
        assert mgr.mark_purged("fact-1")
        assert mgr.active_count == 0

    def test_get_record(self):
        from crp.security.privacy import DataClassification, RetentionManager

        mgr = RetentionManager()
        mgr.register("fact-1", DataClassification.CONFIDENTIAL)
        record = mgr.get_record("fact-1")
        assert record is not None
        assert record.classification == DataClassification.CONFIDENTIAL

    def test_to_dict(self):
        from crp.security.privacy import DataClassification, RetentionManager

        mgr = RetentionManager()
        mgr.register("fact-1", DataClassification.PUBLIC)
        d = mgr.to_dict()
        assert "tracked_count" in d
        assert "active_count" in d


class TestErasureManager:
    def test_create_and_complete_request(self):
        from crp.security.privacy import ErasureManager

        mgr = ErasureManager()
        req = mgr.create_request("user-hash-abc", scope="session")
        assert req.request_id
        assert req.scope == "session"
        assert not req.completed

        pending = mgr.pending_requests()
        assert len(pending) == 1

        assert mgr.complete_request(req.request_id, items_erased=5)

        pending = mgr.pending_requests()
        assert len(pending) == 0

    def test_complete_nonexistent_request(self):
        from crp.security.privacy import ErasureManager

        mgr = ErasureManager()
        assert not mgr.complete_request("nonexistent")

    def test_to_dict(self):
        from crp.security.privacy import ErasureManager

        mgr = ErasureManager()
        mgr.create_request("user-hash", scope="all")
        d = mgr.to_dict()
        assert "pending" in d
        assert "requests" in d


class TestDataLineageTracker:
    def test_record_and_retrieve(self):
        from crp.security.privacy import DataClassification, DataLineageTracker

        tracker = DataLineageTracker()
        entry = tracker.record("fact-1", "ingest", source_label="doc.txt")
        assert entry.data_id == "fact-1"
        assert entry.origin == "ingest"

        retrieved = tracker.get_lineage("fact-1")
        assert retrieved is not None
        assert retrieved.source_label == "doc.txt"

    def test_add_transformation(self):
        from crp.security.privacy import DataLineageTracker

        tracker = DataLineageTracker()
        tracker.record("fact-1", "ingest")
        assert tracker.add_transformation("fact-1", "extraction_stage_2")
        entry = tracker.get_lineage("fact-1")
        assert "extraction_stage_2" in entry.transformations

    def test_reclassify(self):
        from crp.security.privacy import DataClassification, DataLineageTracker

        tracker = DataLineageTracker()
        tracker.record(
            "fact-1", "ingest", classification=DataClassification.PUBLIC
        )
        assert tracker.reclassify("fact-1", DataClassification.RESTRICTED)
        entry = tracker.get_lineage("fact-1")
        assert entry.classification == DataClassification.RESTRICTED

    def test_get_by_classification(self):
        from crp.security.privacy import DataClassification, DataLineageTracker

        tracker = DataLineageTracker()
        tracker.record(
            "fact-1", "ingest", classification=DataClassification.PUBLIC
        )
        tracker.record(
            "fact-2", "ingest", classification=DataClassification.RESTRICTED
        )
        restricted = tracker.get_by_classification(DataClassification.RESTRICTED)
        assert len(restricted) == 1
        assert restricted[0].data_id == "fact-2"

    def test_to_dict(self):
        from crp.security.privacy import DataLineageTracker

        tracker = DataLineageTracker()
        tracker.record("fact-1", "ingest")
        d = tracker.to_dict()
        assert "total_tracked" in d


# ---------------------------------------------------------------------------
# §7.13 — Consent module tests
# ---------------------------------------------------------------------------


class TestConsentManager:
    def test_grant_and_check(self):
        from crp.security.consent import ConsentManager, ProcessingPurpose

        mgr = ConsentManager(session_id="test-session")
        mgr.grant(ProcessingPurpose.ANALYTICS, reason="User opted in")
        assert mgr.check(ProcessingPurpose.ANALYTICS)

    def test_deny(self):
        from crp.security.consent import ConsentManager, ProcessingPurpose

        mgr = ConsentManager(session_id="test-session")
        mgr.deny(ProcessingPurpose.IMPROVEMENT, reason="User declined")
        assert not mgr.check(ProcessingPurpose.IMPROVEMENT)

    def test_withdraw(self):
        from crp.security.consent import ConsentManager, ProcessingPurpose

        mgr = ConsentManager(session_id="test-session")
        mgr.grant(ProcessingPurpose.ANALYTICS)
        assert mgr.check(ProcessingPurpose.ANALYTICS)
        mgr.withdraw(ProcessingPurpose.ANALYTICS)
        assert not mgr.check(ProcessingPurpose.ANALYTICS)

    def test_required_purposes_always_allowed(self):
        from crp.security.consent import ConsentManager, ProcessingPurpose

        mgr = ConsentManager(session_id="test-session")
        # Core purposes should not need explicit consent
        assert mgr.check_required(ProcessingPurpose.CONTEXT_MANAGEMENT)
        assert mgr.check_required(ProcessingPurpose.FACT_EXTRACTION)
        assert mgr.check_required(ProcessingPurpose.SECURITY_SCANNING)

    def test_optional_purposes_need_consent(self):
        from crp.security.consent import ConsentManager, ProcessingPurpose

        mgr = ConsentManager(session_id="test-session")
        # Optional purposes require explicit grant
        assert not mgr.check(ProcessingPurpose.ANALYTICS)
        assert not mgr.check(ProcessingPurpose.IMPROVEMENT)

    def test_consent_state(self):
        from crp.security.consent import ConsentManager, ProcessingPurpose

        mgr = ConsentManager(session_id="test-session")
        mgr.grant(ProcessingPurpose.EXPORT)
        state = mgr.state
        assert state.session_id == "test-session"
        assert state.is_granted(ProcessingPurpose.EXPORT)

    def test_to_dict(self):
        from crp.security.consent import ConsentManager, ProcessingPurpose

        mgr = ConsentManager(session_id="test-session")
        mgr.grant(ProcessingPurpose.ANALYTICS)
        d = mgr.to_dict()
        assert "session_id" in d


class TestProcessingRecordKeeper:
    def test_record_activity(self):
        from crp.security.consent import ProcessingPurpose, ProcessingRecordKeeper

        keeper = ProcessingRecordKeeper(session_id="test-session")
        activity = keeper.record(
            purpose=ProcessingPurpose.FACT_EXTRACTION,
            data_categories=["text", "facts"],
            legal_basis="legitimate_interest",
            input_size_bytes=1024,
        )
        assert activity.purpose == ProcessingPurpose.FACT_EXTRACTION
        assert activity.input_size_bytes == 1024
        assert keeper.activity_count == 1

    def test_export(self):
        from crp.security.consent import ProcessingPurpose, ProcessingRecordKeeper

        keeper = ProcessingRecordKeeper(session_id="test-session")
        keeper.record(
            purpose=ProcessingPurpose.CONTEXT_MANAGEMENT,
            data_categories=["context"],
        )
        exported = keeper.export()
        assert len(exported) == 1
        assert exported[0]["purpose"] == "context_management"

    def test_summary(self):
        from crp.security.consent import ProcessingPurpose, ProcessingRecordKeeper

        keeper = ProcessingRecordKeeper(session_id="test-session")
        keeper.record(
            purpose=ProcessingPurpose.FACT_EXTRACTION,
            data_categories=["text"],
        )
        keeper.record(
            purpose=ProcessingPurpose.FACT_EXTRACTION,
            data_categories=["text"],
        )
        summary = keeper.summary()
        assert summary["total_activities"] == 2


class TestHumanOversightController:
    def test_default_level(self):
        from crp.security.consent import HumanOversightController, HumanOversightLevel

        ctrl = HumanOversightController()
        assert ctrl.level == HumanOversightLevel.INFORMED

    def test_approval_required_when_configured(self):
        from crp.security.consent import (
            HumanOversightController,
            HumanOversightLevel,
            OversightConfig,
        )

        config = OversightConfig(
            level=HumanOversightLevel.APPROVAL,
            require_approval_for_dispatch=True,
        )
        ctrl = HumanOversightController(config=config)
        assert ctrl.requires_approval("dispatch")
        assert not ctrl.requires_approval("ingest")

    def test_autonomous_limit(self):
        from crp.security.consent import HumanOversightController, OversightConfig

        config = OversightConfig(max_autonomous_dispatches=2)
        ctrl = HumanOversightController(config=config)
        assert ctrl.check_autonomous_limit()
        ctrl.record_autonomous_dispatch()
        assert ctrl.check_autonomous_limit()
        ctrl.record_autonomous_dispatch()
        assert not ctrl.check_autonomous_limit()

    def test_request_and_record_decision(self):
        from crp.security.consent import HumanOversightController

        ctrl = HumanOversightController()
        event = ctrl.request_approval("dispatch", {"task": "test"})
        assert event.event_type == "approval_requested"

        decision = ctrl.record_decision(
            event.event_id, approved=True, approved_by="admin"
        )
        assert decision.event_type == "approved"

    def test_halt_on_injection(self):
        from crp.security.consent import HumanOversightController, OversightConfig

        config = OversightConfig(halt_on_injection_detection=True)
        ctrl = HumanOversightController(config=config)
        assert ctrl.should_halt_on_injection()

    def test_halt_on_pii(self):
        from crp.security.consent import HumanOversightController, OversightConfig

        config = OversightConfig(halt_on_pii_detection=True)
        ctrl = HumanOversightController(config=config)
        assert ctrl.should_halt_on_pii()

    def test_record_halt(self):
        from crp.security.consent import HumanOversightController

        ctrl = HumanOversightController()
        event = ctrl.record_halt("dispatch", "PII detected")
        assert event.event_type == "halted"
        assert event.operation == "dispatch"

    def test_to_dict(self):
        from crp.security.consent import HumanOversightController

        ctrl = HumanOversightController()
        d = ctrl.to_dict()
        assert "level" in d
        assert "autonomous_dispatches" in d


# ---------------------------------------------------------------------------
# §7.14 — Audit trail tests
# ---------------------------------------------------------------------------


class TestComplianceAuditTrail:
    def test_record_event(self):
        from crp.security.audit_trail import ComplianceAuditTrail, ComplianceEventType

        trail = ComplianceAuditTrail(session_id="test")
        entry = trail.record(
            ComplianceEventType.DATA_INGESTED,
            session_id="test",
            data={"source": "doc.txt"},
        )
        assert entry.event_type == ComplianceEventType.DATA_INGESTED.value
        assert entry.sequence == 0
        assert trail.entry_count == 1

    def test_chain_integrity(self):
        from crp.security.audit_trail import ComplianceAuditTrail, ComplianceEventType

        trail = ComplianceAuditTrail(session_id="test")
        trail.record(ComplianceEventType.SESSION_CREATED, session_id="test")
        trail.record(ComplianceEventType.DATA_INGESTED, session_id="test")
        trail.record(ComplianceEventType.DATA_PROCESSED, session_id="test")

        valid, broken_at = trail.verify_chain()
        assert valid
        assert broken_at == -1

    def test_query_by_event_type(self):
        from crp.security.audit_trail import ComplianceAuditTrail, ComplianceEventType

        trail = ComplianceAuditTrail(session_id="test")
        trail.record(ComplianceEventType.DATA_INGESTED, session_id="test")
        trail.record(ComplianceEventType.CONSENT_GRANTED, session_id="test")
        trail.record(ComplianceEventType.DATA_INGESTED, session_id="test")

        results = trail.query(event_type=ComplianceEventType.DATA_INGESTED)
        assert len(results) == 2

    def test_query_by_session(self):
        from crp.security.audit_trail import ComplianceAuditTrail, ComplianceEventType

        trail = ComplianceAuditTrail()
        trail.record(ComplianceEventType.DATA_INGESTED, session_id="s1")
        trail.record(ComplianceEventType.DATA_INGESTED, session_id="s2")

        results = trail.query(session_id="s1")
        assert len(results) == 1

    def test_export(self):
        from crp.security.audit_trail import ComplianceAuditTrail, ComplianceEventType

        trail = ComplianceAuditTrail(session_id="test")
        trail.record(ComplianceEventType.SESSION_CREATED, session_id="test")
        trail.record(ComplianceEventType.DATA_INGESTED, session_id="test")

        export = trail.export()
        assert "entries" in export
        assert len(export["entries"]) == 2

    def test_export_jsonl(self):
        from crp.security.audit_trail import ComplianceAuditTrail, ComplianceEventType

        trail = ComplianceAuditTrail(session_id="test")
        trail.record(ComplianceEventType.SESSION_CREATED, session_id="test")

        jsonl = trail.export_jsonl()
        assert jsonl.strip()  # Non-empty
        import json

        line = json.loads(jsonl.strip().split("\n")[0])
        assert "event_type" in line

    def test_hmac_signing(self):
        from crp.security.audit_trail import ComplianceAuditTrail, ComplianceEventType

        trail = ComplianceAuditTrail(session_id="test")
        entry = trail.record(ComplianceEventType.DATA_INGESTED, session_id="test")
        # Signature should be a hex string (HMAC-SHA256 = 64 hex chars)
        assert len(entry.signature) == 64
        assert entry.entry_hash  # Non-empty hash

    def test_chained_previous_hash(self):
        from crp.security.audit_trail import ComplianceAuditTrail, ComplianceEventType

        trail = ComplianceAuditTrail(session_id="test")
        e1 = trail.record(ComplianceEventType.SESSION_CREATED, session_id="test")
        e2 = trail.record(ComplianceEventType.DATA_INGESTED, session_id="test")

        # First entry has genesis previous_hash
        assert e1.previous_hash == "0" * 64
        # Second entry chains to first entry's hash
        assert e2.previous_hash == e1.entry_hash

    def test_multiple_events_diverse(self):
        from crp.security.audit_trail import ComplianceAuditTrail, ComplianceEventType

        trail = ComplianceAuditTrail(session_id="test")
        for evt in [
            ComplianceEventType.SESSION_CREATED,
            ComplianceEventType.DATA_INGESTED,
            ComplianceEventType.PII_DETECTED,
            ComplianceEventType.CONSENT_GRANTED,
            ComplianceEventType.OVERSIGHT_APPROVAL_REQUESTED,
            ComplianceEventType.SESSION_CLOSED,
        ]:
            trail.record(evt, session_id="test")

        assert trail.entry_count == 6
        valid, _ = trail.verify_chain()
        assert valid


# ---------------------------------------------------------------------------
# §7.15 — Compliance module tests
# ---------------------------------------------------------------------------


class TestRiskClassifier:
    def test_minimal_risk_default(self):
        from crp.security.compliance import AIRiskLevel, RiskClassifier

        classifier = RiskClassifier()
        assessment = classifier.assess()
        assert assessment.risk_level == AIRiskLevel.MINIMAL

    def test_high_risk_employment(self):
        from crp.security.compliance import (
            AIRiskLevel,
            AISystemCategory,
            RiskClassifier,
        )

        classifier = RiskClassifier()
        assessment = classifier.assess(category=AISystemCategory.EMPLOYMENT)
        assert assessment.risk_level == AIRiskLevel.HIGH

    def test_high_risk_healthcare(self):
        from crp.security.compliance import (
            AIRiskLevel,
            AISystemCategory,
            RiskClassifier,
        )

        classifier = RiskClassifier()
        assessment = classifier.assess(category=AISystemCategory.HEALTHCARE)
        assert assessment.risk_level == AIRiskLevel.HIGH

    def test_high_risk_profiling(self):
        from crp.security.compliance import AIRiskLevel, RiskClassifier

        classifier = RiskClassifier()
        assessment = classifier.assess(profiles_individuals=True)
        assert assessment.risk_level == AIRiskLevel.HIGH

    def test_high_risk_safety_critical(self):
        from crp.security.compliance import AIRiskLevel, RiskClassifier

        classifier = RiskClassifier()
        assessment = classifier.assess(safety_critical=True)
        assert assessment.risk_level == AIRiskLevel.HIGH

    def test_high_risk_automated_decisions_fundamental_rights(self):
        from crp.security.compliance import AIRiskLevel, RiskClassifier

        classifier = RiskClassifier()
        assessment = classifier.assess(
            makes_automated_decisions=True,
            affects_fundamental_rights=True,
        )
        assert assessment.risk_level == AIRiskLevel.HIGH

    def test_limited_risk_content_generation(self):
        from crp.security.compliance import (
            AIRiskLevel,
            AISystemCategory,
            RiskClassifier,
        )

        classifier = RiskClassifier()
        assessment = classifier.assess(
            category=AISystemCategory.CONTENT_GENERATION,
        )
        assert assessment.risk_level == AIRiskLevel.LIMITED

    def test_limited_risk_personal_data(self):
        from crp.security.compliance import AIRiskLevel, RiskClassifier

        classifier = RiskClassifier()
        assessment = classifier.assess(processes_personal_data=True)
        assert assessment.risk_level == AIRiskLevel.LIMITED

    def test_assessment_includes_mitigations(self):
        from crp.security.compliance import RiskClassifier

        classifier = RiskClassifier()
        assessment = classifier.assess()
        assert len(assessment.mitigations) > 0

    def test_assessment_includes_residual_risks(self):
        from crp.security.compliance import AIRiskLevel, RiskClassifier

        classifier = RiskClassifier()
        assessment = classifier.assess(processes_personal_data=True)
        assert len(assessment.residual_risks) > 0

    def test_assessment_to_dict(self):
        from crp.security.compliance import RiskClassifier

        classifier = RiskClassifier()
        assessment = classifier.assess()
        d = assessment.to_dict()
        assert "risk_level" in d
        assert "risk_factors" in d
        assert "mitigations" in d


class TestTransparencyDeclaration:
    def test_default_values(self):
        from crp.security.compliance import TransparencyDeclaration

        decl = TransparencyDeclaration()
        assert decl.system_name == "Context Relay Protocol (CRP)"
        assert decl.provider == "AutoCyber AI Pty Ltd"
        assert len(decl.data_processed) > 0
        assert len(decl.limitations) > 0

    def test_to_dict(self):
        from crp.security.compliance import TransparencyDeclaration

        decl = TransparencyDeclaration(system_version="2.0.0")
        d = decl.to_dict()
        assert d["system_version"] == "2.0.0"
        assert "data_processed" in d
        assert "data_not_processed" in d


class TestComplianceReporter:
    def test_generate_report(self):
        from crp.security.compliance import ComplianceReporter

        reporter = ComplianceReporter()
        report = reporter.generate_report()
        assert "frameworks" in report
        assert "eu_ai_act" in report["frameworks"]
        assert "iso_42001" in report["frameworks"]
        assert report["summary"]["compliance_score"] > 0

    def test_eu_ai_act_controls(self):
        from crp.security.compliance import ComplianceReporter

        reporter = ComplianceReporter()
        report = reporter.generate_report()
        eu = report["frameworks"]["eu_ai_act"]
        assert eu["total_controls"] == 8  # Art. 9-17
        assert eu["implemented"] == 8  # All implemented

    def test_iso_42001_controls(self):
        from crp.security.compliance import ComplianceReporter

        reporter = ComplianceReporter()
        report = reporter.generate_report()
        iso = report["frameworks"]["iso_42001"]
        assert iso["total_controls"] == 8
        assert iso["implemented"] == 8

    def test_report_with_risk_assessment(self):
        from crp.security.compliance import ComplianceReporter, RiskClassifier

        classifier = RiskClassifier()
        assessment = classifier.assess(processes_personal_data=True)
        reporter = ComplianceReporter()
        report = reporter.generate_report(risk_assessment=assessment)
        assert "risk_assessment" in report

    def test_generate_technical_documentation(self):
        from crp.security.compliance import ComplianceReporter, TransparencyDeclaration

        reporter = ComplianceReporter()
        decl = TransparencyDeclaration(system_version="2.0.0")
        doc = reporter.generate_technical_documentation(transparency=decl)
        assert doc["document_type"] == "technical_documentation"
        assert doc["system"]["name"] == "Context Relay Protocol (CRP)"
        assert "architecture" in doc
        assert "security_measures" in doc
        assert "human_oversight" in doc
        assert "compliance_controls" in doc


# ---------------------------------------------------------------------------
# Integration tests — cross-module interactions
# ---------------------------------------------------------------------------


class TestCrossModuleIntegration:
    def test_pii_scan_triggers_classification_and_audit(self):
        """PII detection → classification → audit trail entry."""
        from crp.security.audit_trail import ComplianceAuditTrail, ComplianceEventType
        from crp.security.privacy import DataClassification, DataLineageTracker, PIIScanner

        scanner = PIIScanner()
        tracker = DataLineageTracker()
        trail = ComplianceAuditTrail(session_id="test")

        # Scan text with PII
        result = scanner.scan("Contact: user@example.com, SSN: 123-45-6789")
        assert result.has_pii

        # Track lineage with elevated classification
        entry = tracker.record(
            "fact-1", "ingest",
            classification=result.highest_classification,
        )
        assert entry.classification >= DataClassification.RESTRICTED

        # Record in audit trail
        trail.record(
            ComplianceEventType.PII_DETECTED,
            session_id="test",
            data={
                "pii_types": list(result.pii_types_found),
                "classification": entry.classification.name,
            },
        )
        assert trail.entry_count == 1

    def test_consent_check_with_processing_record(self):
        """Consent grant → processing record → audit trail."""
        from crp.security.audit_trail import ComplianceAuditTrail, ComplianceEventType
        from crp.security.consent import (
            ConsentManager,
            ProcessingPurpose,
            ProcessingRecordKeeper,
        )

        consent = ConsentManager(session_id="test")
        records = ProcessingRecordKeeper(session_id="test")
        trail = ComplianceAuditTrail(session_id="test")

        # Grant consent for analytics
        consent.grant(ProcessingPurpose.ANALYTICS)
        trail.record(
            ComplianceEventType.CONSENT_GRANTED,
            session_id="test",
            data={"purpose": ProcessingPurpose.ANALYTICS.value},
        )

        # Record processing activity
        if consent.check(ProcessingPurpose.ANALYTICS):
            records.record(
                purpose=ProcessingPurpose.ANALYTICS,
                data_categories=["usage_metrics"],
                legal_basis="consent",
            )

        assert records.activity_count == 1
        assert trail.entry_count == 1

    def test_full_compliance_pipeline(self):
        """Full pipeline: risk → consent → process → audit → report."""
        from crp.security.audit_trail import ComplianceAuditTrail, ComplianceEventType
        from crp.security.compliance import ComplianceReporter, RiskClassifier
        from crp.security.consent import (
            ConsentManager,
            ProcessingPurpose,
            ProcessingRecordKeeper,
        )

        # 1. Risk assessment
        classifier = RiskClassifier()
        risk = classifier.assess(processes_personal_data=True)

        # 2. Set up consent
        consent = ConsentManager(session_id="test")

        # 3. Process with records
        records = ProcessingRecordKeeper(session_id="test")
        records.record(
            purpose=ProcessingPurpose.CONTEXT_MANAGEMENT,
            data_categories=["text"],
        )

        # 4. Audit trail
        trail = ComplianceAuditTrail(session_id="test")
        trail.record(ComplianceEventType.RISK_ASSESSMENT, session_id="test")
        trail.record(ComplianceEventType.DATA_PROCESSED, session_id="test")

        # 5. Compliance report
        reporter = ComplianceReporter()
        report = reporter.generate_report(
            risk_assessment=risk,
            session_stats={"processing_activities": records.activity_count},
        )

        assert report["summary"]["compliance_score"] == 100.0
        assert report["risk_assessment"]["risk_level"] == "limited"


# ---------------------------------------------------------------------------
# Import tests — verify public API surface
# ---------------------------------------------------------------------------


class TestPublicAPI:
    def test_import_from_security_package(self):
        from crp.security import (
            AIRiskLevel,
            AISystemCategory,
            ComplianceAuditTrail,
            ComplianceEventType,
            ComplianceReporter,
            ConsentManager,
            DataClassification,
            DataLineageTracker,
            ErasureManager,
            HumanOversightController,
            HumanOversightLevel,
            PIIScanner,
            ProcessingPurpose,
            ProcessingRecordKeeper,
            RetentionManager,
            RiskAssessment,
            RiskClassifier,
            TransparencyDeclaration,
        )

        # Just verify they're importable and are the right types
        assert PIIScanner is not None
        assert ConsentManager is not None
        assert ComplianceAuditTrail is not None
        assert RiskClassifier is not None
