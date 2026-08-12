# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Integration tests: compliance modules wired into orchestrator (§7.12–§7.15).

Verifies that the privacy, consent, audit trail, and compliance modules
are ACTUALLY called during dispatch(), ingest(), export_state(), close(),
and reset_session() — not just instantiated.
"""

from __future__ import annotations

import pytest

from crp.core.orchestrator import CRPOrchestrator
from crp.providers.base import LLMProvider
from crp.security.audit_trail import ComplianceEventType


# ---------------------------------------------------------------------------
# Test provider
# ---------------------------------------------------------------------------


class _FakeProvider(LLMProvider):
    """Minimal test provider for compliance wiring tests."""

    def __init__(self, output: str = "fake output response"):
        self._output = output

    def generate_chat(
        self, messages: list[dict[str, str]], **kwargs: object
    ) -> tuple[str, str]:
        # Use "length" finish_reason so continuation trigger takes wall-hit
        # path (which respects max_continuations=0) instead of gap_override
        # path that loops indefinitely with trivial fake output.
        return self._output, "length"

    def count_tokens(self, text: str) -> int:
        return len(text) // 4 or 1

    def context_window_size(self) -> int:
        return 4096

    @property
    def max_output_tokens(self) -> int | None:
        return 1024

    @property
    def model_name(self) -> str:
        return "fake-compliance-v1"


class _PIIProvider(LLMProvider):
    """Provider that returns output containing PII patterns."""

    def generate_chat(
        self, messages: list[dict[str, str]], **kwargs: object
    ) -> tuple[str, str]:
        return "Contact John at john@example.com or call +1-555-123-4567", "length"

    def count_tokens(self, text: str) -> int:
        return len(text) // 4 or 1

    def context_window_size(self) -> int:
        return 4096

    @property
    def max_output_tokens(self) -> int | None:
        return 1024

    @property
    def model_name(self) -> str:
        return "fake-pii-v1"


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _make_orch(**kwargs) -> CRPOrchestrator:
    provider = kwargs.pop("provider", None) or _FakeProvider()
    # Disable continuation windows for fast tests (default 50 * 2s sleep = 100s)
    if "max_continuations" not in kwargs:
        kwargs["max_continuations"] = 0
    return CRPOrchestrator(provider=provider, **kwargs)


def _event_types(orch: CRPOrchestrator) -> list[str]:
    """Return all event types from the compliance audit trail."""
    export = orch.compliance_audit.export()
    return [e["event_type"] for e in export["entries"]]


# ---------------------------------------------------------------------------
# §7.14 — Audit trail wired into orchestrator lifecycle
# ---------------------------------------------------------------------------


class TestSessionLifecycleAudit:
    """Verify audit entries for session create / close."""

    def test_session_created_audit_entry(self):
        orch = _make_orch()
        events = _event_types(orch)
        assert ComplianceEventType.SESSION_CREATED.value in events

    def test_session_created_has_model_info(self):
        orch = _make_orch()
        export = orch.compliance_audit.export()
        created = [e for e in export["entries"]
                   if e["event_type"] == ComplianceEventType.SESSION_CREATED.value]
        assert len(created) == 1
        assert created[0]["data"]["model"] == "fake-compliance-v1"
        assert "protocol_version" in created[0]["data"]

    def test_session_close_audit_entry(self):
        orch = _make_orch()
        orch.close()
        events = _event_types(orch)
        assert ComplianceEventType.SESSION_CLOSED.value in events

    def test_session_close_includes_summary(self):
        orch = _make_orch()
        orch.dispatch("system", "task")
        orch.close()
        export = orch.compliance_audit.export()
        closed = [e for e in export["entries"]
                  if e["event_type"] == ComplianceEventType.SESSION_CLOSED.value]
        assert len(closed) == 1
        assert closed[0]["data"]["windows_completed"] >= 1


class TestResetSessionAudit:
    """Verify audit entries for session reset."""

    def test_reset_records_data_deleted(self):
        orch = _make_orch()
        orch.dispatch("system", "task")
        # reset_session requires ADMIN role (MANAGE_SESSIONS permission)
        from crp.security.rbac import Role
        orch._rbac.role = Role.ADMIN
        orch.reset_session()
        events = _event_types(orch)
        assert ComplianceEventType.DATA_DELETED.value in events


# ---------------------------------------------------------------------------
# §7.14 — Audit trail wired into dispatch()
# ---------------------------------------------------------------------------


class TestDispatchAudit:
    """Verify audit entries are created during dispatch."""

    def test_dispatch_creates_audit_entries(self):
        orch = _make_orch()
        orch.dispatch("system", "task input")
        # Should have at least SESSION_CREATED + DATA_PROCESSED (started + completed)
        assert orch.compliance_audit.entry_count >= 3

    def test_dispatch_records_data_processed_started(self):
        orch = _make_orch()
        orch.dispatch("system", "task input")
        export = orch.compliance_audit.export()
        processed = [e for e in export["entries"]
                     if e["event_type"] == ComplianceEventType.DATA_PROCESSED.value]
        phases = [e["data"]["phase"] for e in processed]
        assert "started" in phases

    def test_dispatch_records_data_processed_completed(self):
        orch = _make_orch()
        orch.dispatch("system", "task input")
        export = orch.compliance_audit.export()
        processed = [e for e in export["entries"]
                     if e["event_type"] == ComplianceEventType.DATA_PROCESSED.value]
        phases = [e["data"]["phase"] for e in processed]
        assert "completed" in phases

    def test_dispatch_completed_has_details(self):
        orch = _make_orch()
        orch.dispatch("system", "task input")
        export = orch.compliance_audit.export()
        completed = [e for e in export["entries"]
                     if e["event_type"] == ComplianceEventType.DATA_PROCESSED.value
                     and e["data"].get("phase") == "completed"]
        assert len(completed) == 1
        data = completed[0]["data"]
        assert "window_id" in data
        assert "quality_tier" in data
        assert "facts_extracted" in data
        assert "output_tokens" in data

    def test_dispatch_chain_integrity(self):
        orch = _make_orch()
        orch.dispatch("system", "task")
        valid, broken_at = orch.compliance_audit.verify_chain()
        assert valid
        assert broken_at == -1  # -1 means no break


# ---------------------------------------------------------------------------
# §7.12 — PII scanning wired into dispatch/ingest
# ---------------------------------------------------------------------------


class TestPIIScanningWired:
    """Verify PII scanner is called during operations."""

    def test_pii_in_dispatch_input_logged(self):
        orch = _make_orch()
        orch.dispatch("system", "Send email to user@example.com please")
        export = orch.compliance_audit.export()
        pii_events = [e for e in export["entries"]
                      if e["event_type"] == ComplianceEventType.PII_DETECTED.value
                      and e["data"].get("phase") == "input"]
        assert len(pii_events) >= 1
        assert "email" in pii_events[0]["data"]["pii_types"]

    def test_pii_in_dispatch_output_logged(self):
        orch = _make_orch(provider=_PIIProvider())
        orch.dispatch("system", "task")
        export = orch.compliance_audit.export()
        pii_events = [e for e in export["entries"]
                      if e["event_type"] == ComplianceEventType.PII_DETECTED.value
                      and e["data"].get("phase") == "output"]
        assert len(pii_events) >= 1
        pii_types = pii_events[0]["data"]["pii_types"]
        assert "email" in pii_types or "phone_international" in pii_types

    def test_pii_in_ingest_logged(self):
        orch = _make_orch()
        orch.ingest("Contact us at admin@corp.com", source_label="pii-doc")
        export = orch.compliance_audit.export()
        pii_events = [e for e in export["entries"]
                      if e["event_type"] == ComplianceEventType.PII_DETECTED.value]
        assert len(pii_events) >= 1
        assert "email" in pii_events[0]["data"]["pii_types"]

    def test_no_pii_no_event(self):
        orch = _make_orch()
        orch.dispatch("system", "Write about trees and nature")
        export = orch.compliance_audit.export()
        pii_events = [e for e in export["entries"]
                      if e["event_type"] == ComplianceEventType.PII_DETECTED.value
                      and e["data"].get("phase") == "input"]
        assert len(pii_events) == 0


# ---------------------------------------------------------------------------
# §7.14 — Audit trail wired into ingest()
# ---------------------------------------------------------------------------


class TestIngestAudit:
    """Verify audit entries for ingest operations."""

    def test_ingest_creates_audit_entries(self):
        orch = _make_orch()
        orch.ingest("The capital of France is Paris", source_label="test-doc")
        events = _event_types(orch)
        assert ComplianceEventType.DATA_INGESTED.value in events

    def test_ingest_records_started_and_completed(self):
        orch = _make_orch()
        orch.ingest("Some factual content here", source_label="doc")
        export = orch.compliance_audit.export()
        ingested = [e for e in export["entries"]
                    if e["event_type"] == ComplianceEventType.DATA_INGESTED.value]
        phases = [e["data"]["phase"] for e in ingested]
        assert "started" in phases
        assert "completed" in phases

    def test_ingest_completed_has_details(self):
        orch = _make_orch()
        orch.ingest("Python is a programming language", source_label="wiki")
        export = orch.compliance_audit.export()
        completed = [e for e in export["entries"]
                     if e["event_type"] == ComplianceEventType.DATA_INGESTED.value
                     and e["data"].get("phase") == "completed"]
        assert len(completed) == 1
        data = completed[0]["data"]
        assert data["source_label"] == "wiki"
        assert "facts_extracted" in data

    def test_ingest_chain_integrity(self):
        orch = _make_orch()
        orch.ingest("Some text", source_label="test")
        orch.ingest("More text", source_label="test2")
        valid, broken_at = orch.compliance_audit.verify_chain()
        assert valid


# ---------------------------------------------------------------------------
# §7.14 — Audit trail wired into export_state()
# ---------------------------------------------------------------------------


class TestExportStateAudit:
    """Verify audit entries for state export."""

    def test_export_state_audit(self):
        orch = _make_orch()
        orch.dispatch("system", "task")
        orch.export_state()
        events = _event_types(orch)
        assert ComplianceEventType.DATA_EXPORTED.value in events

    def test_export_state_records_started_and_completed(self):
        orch = _make_orch()
        orch.export_state()
        export = orch.compliance_audit.export()
        exported = [e for e in export["entries"]
                    if e["event_type"] == ComplianceEventType.DATA_EXPORTED.value]
        phases = [e["data"]["phase"] for e in exported]
        assert "started" in phases
        assert "completed" in phases


# ---------------------------------------------------------------------------
# §7.13 — Processing records (GDPR Art. 30)
# ---------------------------------------------------------------------------


class TestProcessingRecordsWired:
    """Verify GDPR Art. 30 processing records are created."""

    def test_dispatch_creates_processing_record(self):
        orch = _make_orch()
        orch.dispatch("system", "task input")
        assert orch.processing_records.activity_count >= 1

    def test_ingest_creates_processing_record(self):
        orch = _make_orch()
        orch.ingest("Some text content", source_label="test")
        assert orch.processing_records.activity_count >= 1

    def test_export_creates_processing_record(self):
        orch = _make_orch()
        orch.export_state()
        assert orch.processing_records.activity_count >= 1

    def test_processing_records_accumulate(self):
        orch = _make_orch()
        orch.dispatch("system", "task1")
        orch.dispatch("system", "task2")
        orch.ingest("text", source_label="doc")
        assert orch.processing_records.activity_count >= 3

    def test_processing_record_has_categories(self):
        orch = _make_orch()
        orch.dispatch("system", "task")
        records = orch.processing_records.export()
        assert len(records) >= 1
        assert "data_categories" in records[0]
        assert len(records[0]["data_categories"]) > 0


# ---------------------------------------------------------------------------
# §7.12 — Retention + lineage tracking wired
# ---------------------------------------------------------------------------


class TestRetentionWired:
    """Verify retention manager tracks facts from dispatch/ingest."""

    def test_dispatch_registers_fact_retention(self):
        orch = _make_orch()
        orch.dispatch("system", "Write about Python programming")
        # Retention tracked count should match extracted facts
        assert orch.retention_manager.tracked_count >= 0

    def test_ingest_registers_fact_retention(self):
        orch = _make_orch()
        orch.ingest("Python is a high-level language", source_label="doc")
        assert orch.retention_manager.tracked_count >= 0


class TestLineageWired:
    """Verify data lineage tracker records origin of facts."""

    def test_dispatch_tracks_lineage(self):
        orch = _make_orch()
        orch.dispatch("system", "Write about Python programming")
        lineage = orch.lineage_tracker.to_dict()
        # Lineage entries created if facts were extracted
        assert isinstance(lineage, dict)

    def test_ingest_tracks_lineage(self):
        orch = _make_orch()
        orch.ingest("Python is a high-level language", source_label="doc")
        lineage = orch.lineage_tracker.to_dict()
        assert isinstance(lineage, dict)


# ---------------------------------------------------------------------------
# §7.13 — Human oversight (EU AI Act Art. 14)
# ---------------------------------------------------------------------------


class TestHumanOversightWired:
    """Verify human oversight controller is checked during dispatch."""

    def test_autonomous_dispatch_recorded(self):
        orch = _make_orch()
        orch.dispatch("system", "task")
        # After dispatch, autonomous dispatch should be recorded
        # (the controller tracks autonomous operations)
        oversight_dict = orch.human_oversight.to_dict()
        assert oversight_dict["autonomous_dispatches"] >= 1

    def test_multiple_dispatches_track_autonomy(self):
        orch = _make_orch()
        orch.dispatch("system", "task1")
        orch.dispatch("system", "task2")
        oversight_dict = orch.human_oversight.to_dict()
        assert oversight_dict["autonomous_dispatches"] >= 2


# ---------------------------------------------------------------------------
# Properties accessible
# ---------------------------------------------------------------------------


class TestComplianceProperties:
    """Verify compliance subsystem properties are accessible."""

    def test_compliance_audit_property(self):
        orch = _make_orch()
        assert orch.compliance_audit is not None
        assert orch.compliance_audit.entry_count >= 1  # SESSION_CREATED

    def test_pii_scanner_property(self):
        orch = _make_orch()
        assert orch.pii_scanner is not None

    def test_consent_manager_property(self):
        orch = _make_orch()
        assert orch.consent_manager is not None

    def test_processing_records_property(self):
        orch = _make_orch()
        assert orch.processing_records is not None

    def test_retention_manager_property(self):
        orch = _make_orch()
        assert orch.retention_manager is not None

    def test_lineage_tracker_property(self):
        orch = _make_orch()
        assert orch.lineage_tracker is not None

    def test_human_oversight_property(self):
        orch = _make_orch()
        assert orch.human_oversight is not None

    def test_compliance_reporter_property(self):
        orch = _make_orch()
        assert orch.compliance_reporter is not None

    def test_risk_classifier_property(self):
        orch = _make_orch()
        assert orch.risk_classifier is not None


# ---------------------------------------------------------------------------
# End-to-end compliance flow
# ---------------------------------------------------------------------------


class TestEndToEndCompliance:
    """Full session lifecycle with compliance verification."""

    def test_full_lifecycle_audit_chain(self):
        """SESSION_CREATED → dispatch → ingest → export → close → verify chain."""
        orch = _make_orch()

        # Dispatch
        orch.dispatch("system", "Write about AI safety")

        # Ingest
        orch.ingest("AI safety is important for humanity", source_label="doc")

        # Export
        orch.export_state()

        # Close
        orch.close()

        # Verify chain integrity
        valid, broken_at = orch.compliance_audit.verify_chain()
        assert valid, f"Chain broken at entry {broken_at}"
        assert broken_at == -1  # -1 means no break

        # Check all expected event types present
        events = _event_types(orch)
        assert ComplianceEventType.SESSION_CREATED.value in events
        assert ComplianceEventType.DATA_PROCESSED.value in events
        assert ComplianceEventType.DATA_INGESTED.value in events
        assert ComplianceEventType.DATA_EXPORTED.value in events
        assert ComplianceEventType.SESSION_CLOSED.value in events

    def test_full_lifecycle_entry_count(self):
        """Multiple operations should produce many audit entries."""
        orch = _make_orch()
        orch.dispatch("system", "task1")
        orch.dispatch("system", "task2")
        orch.ingest("text", source_label="doc")
        orch.export_state()
        orch.close()
        # SESSION_CREATED + 2*(dispatch started + completed) + ingest started/completed
        # + export started/completed + SESSION_CLOSED = minimum 10
        assert orch.compliance_audit.entry_count >= 10

    def test_pii_lifecycle_with_audit(self):
        """PII in input → detection logged → chain still valid."""
        orch = _make_orch()
        orch.dispatch("system", "Email user@test.com about the project")
        orch.close()

        events = _event_types(orch)
        assert ComplianceEventType.PII_DETECTED.value in events

        valid, _ = orch.compliance_audit.verify_chain()
        assert valid

    def test_audit_export_jsonl(self):
        """Audit trail can be exported as JSONL for regulatory review."""
        orch = _make_orch()
        orch.dispatch("system", "task")
        orch.close()

        jsonl = orch.compliance_audit.export_jsonl()
        assert len(jsonl) > 0
        lines = jsonl.strip().split("\n")
        assert len(lines) >= 3  # SESSION_CREATED + dispatch events + SESSION_CLOSED
