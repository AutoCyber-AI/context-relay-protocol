# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Transcript capture for the compliance audit chain (§7.14, schema 2.1.0).

Implements docs/FIX_NOTE_transcript_capture.md:
  - TRANSCRIPT_RECORDED emitted per window when enabled; absent when disabled
  - stored transcript hashes verifiably match chain entries (verify_transcripts)
  - PII redaction honored; redaction state recorded on the event
  - size cap honored; oversized outputs truncated with full-content hash kept
  - export_jsonl(..., include_transcripts=True) self-contained bundle
  - INCIDENT_* event types with validated payload shapes (WASA self-healing)
  - QUARANTINE_VALIDATED counters exposed on the compliance chain (§7.8)
"""

from __future__ import annotations

import json

import pytest

from crp.core.orchestrator import CRPOrchestrator
from crp.providers.base import LLMProvider
from crp.security.audit_trail import (
    INCIDENT_PAYLOAD_SHAPES,
    ComplianceAuditTrail,
    ComplianceEventType,
    validate_incident_payload,
)
from crp.security.privacy import PIIScanner
from crp.security.transcript_store import (
    TRANSCRIPT_SCHEMA_VERSION,
    TranscriptRecord,
    TranscriptStore,
    hash_text,
    redact_text,
    verify_transcripts,
)

# ---------------------------------------------------------------------------
# Test providers
# ---------------------------------------------------------------------------


class _FakeProvider(LLMProvider):
    """Deterministic provider; 'length' finish keeps continuation inert."""

    def __init__(self, output: str = "fake output response"):
        self._output = output

    def generate_chat(
        self, messages: list[dict[str, str]], **kwargs: object
    ) -> tuple[str, str]:
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
        return "fake-transcript-v1"


class _PIIProvider(_FakeProvider):
    """Provider returning output containing PII patterns."""

    def generate_chat(
        self, messages: list[dict[str, str]], **kwargs: object
    ) -> tuple[str, str]:
        return "Contact John at john@example.com or call +1-555-123-4567", "length"

    @property
    def model_name(self) -> str:
        return "fake-pii-v1"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_orch(tmp_path=None, **kwargs) -> CRPOrchestrator:
    provider = kwargs.pop("provider", None) or _FakeProvider()
    if "max_continuations" not in kwargs:
        kwargs["max_continuations"] = 0
    if tmp_path is not None and "audit_transcript_dir" not in kwargs:
        kwargs["audit_transcript_dir"] = str(tmp_path / "transcripts")
    return CRPOrchestrator(provider=provider, **kwargs)


def _entries(orch: CRPOrchestrator, event_type: ComplianceEventType) -> list[dict]:
    export = orch.compliance_audit.export()
    return [
        e for e in export["entries"] if e["event_type"] == event_type.value
    ]


# ---------------------------------------------------------------------------
# Capture on/off
# ---------------------------------------------------------------------------


class TestTranscriptCaptureOnOff:
    def test_off_by_default_no_event(self):
        orch = _make_orch()
        orch.dispatch("system", "task")
        assert _entries(orch, ComplianceEventType.TRANSCRIPT_RECORDED) == []
        assert orch.compliance_audit.transcript_store is None

    def test_off_by_default_verify_transcripts_raises(self):
        orch = _make_orch()
        orch.dispatch("system", "task")
        with pytest.raises(ValueError, match="No transcript store attached"):
            orch.compliance_audit.verify_transcripts()

    def test_on_emits_event_per_window(self, tmp_path):
        # Explicit opt-out: redaction now defaults ON whenever capture is on
        # (U-C3); this test covers the raw (non-redacted) storage path.
        orch = _make_orch(
            tmp_path,
            audit_capture_transcripts=True,
            audit_transcript_redact_pii=False,
        )
        orch.dispatch("system", "task")
        events = _entries(orch, ComplianceEventType.TRANSCRIPT_RECORDED)
        assert len(events) == 1
        data = events[0]["data"]
        assert data["window_id"]
        assert data["raw_output_id"]
        assert data["input_hash"] == hash_text("task")[:16]
        assert data["output_hash"] == hash_text("fake output response")[:16]
        assert data["redacted"] is False
        assert data["pii_types"] == []
        assert data["bytes_out"] == len("fake output response")
        assert data["transcript_ref"]

    def test_on_env_var_flag(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CRP_AUDIT_CAPTURE_TRANSCRIPTS", "true")
        monkeypatch.setenv("CRP_AUDIT_TRANSCRIPT_DIR", str(tmp_path / "env transcripts"))
        orch = _make_orch()
        orch.dispatch("system", "task")
        assert len(_entries(orch, ComplianceEventType.TRANSCRIPT_RECORDED)) == 1
        assert (tmp_path / "env transcripts").is_dir()

    def test_raw_output_id_stops_dangling(self, tmp_path):
        orch = _make_orch(tmp_path, audit_capture_transcripts=True)
        orch.dispatch("system", "task")
        events = _entries(orch, ComplianceEventType.TRANSCRIPT_RECORDED)
        store = orch.compliance_audit.transcript_store
        assert store is not None
        record = store.get(events[0]["data"]["raw_output_id"])
        assert record is not None
        assert record.output == "fake output response"
        assert any(m.get("role") == "user" for m in record.messages)

    def test_memory_only_store_when_no_dir(self):
        orch = _make_orch(None, audit_capture_transcripts=True)
        orch.dispatch("system", "task")
        store = orch.compliance_audit.transcript_store
        assert store is not None
        assert store.storage_dir is None
        events = _entries(orch, ComplianceEventType.TRANSCRIPT_RECORDED)
        assert store.get(events[0]["data"]["raw_output_id"]) is not None

    def test_continuation_windows_each_emit_event(self, tmp_path):
        """Primary + each continuation window gets its own transcript (§3)."""
        orch = CRPOrchestrator(
            provider=_FakeProvider(),
            max_continuations=2,
            audit_capture_transcripts=True,
            audit_transcript_dir=str(tmp_path / "tx"),
        )
        orch.dispatch("system", "task")
        events = _entries(orch, ComplianceEventType.TRANSCRIPT_RECORDED)
        assert len(events) >= 2
        primary = [e for e in events if e["data"]["window_type"] == "primary"]
        conts = [e for e in events if e["data"]["window_type"] == "continuation"]
        assert len(primary) == 1
        assert len(conts) == len(events) - 1
        assert all(e["data"]["continuation_index"] >= 1 for e in conts)


# ---------------------------------------------------------------------------
# Hash linkage + verification
# ---------------------------------------------------------------------------


class TestVerifyTranscripts:
    def test_hashes_match_llm_call_completed(self, tmp_path):
        orch = _make_orch(tmp_path, audit_capture_transcripts=True)
        orch.dispatch("system", "task")
        llm_calls = _entries(orch, ComplianceEventType.LLM_CALL_COMPLETED)
        transcripts = _entries(orch, ComplianceEventType.TRANSCRIPT_RECORDED)
        assert len(llm_calls) == 1 and len(transcripts) == 1
        # Same truncated-sha256 convention as the chain entry.
        assert (
            transcripts[0]["data"]["input_hash"]
            == llm_calls[0]["data"]["task_input_hash"]
        )
        assert (
            transcripts[0]["data"]["system_prompt_hash"]
            == llm_calls[0]["data"]["system_prompt_hash"]
        )

    def test_verify_transcripts_green(self, tmp_path):
        orch = _make_orch(tmp_path, audit_capture_transcripts=True)
        orch.dispatch("system", "task")
        orch.dispatch("system", "second task")
        result = orch.compliance_audit.verify_transcripts()
        assert result.valid, result.mismatches
        assert result.checked == 2
        assert result.missing == []

    def test_tamper_detected_at_exact_window(self, tmp_path):
        orch = _make_orch(tmp_path, audit_capture_transcripts=True)
        orch.dispatch("system", "task one")
        orch.dispatch("system", "task two")
        events = _entries(orch, ComplianceEventType.TRANSCRIPT_RECORDED)
        assert len(events) == 2
        tampered_window = events[1]["data"]["window_id"]
        store = orch.compliance_audit.transcript_store
        record = store.get(events[1]["data"]["raw_output_id"])
        # Simulate post-hoc tampering with the stored transcript file.
        record.output = "EVIL EDITED OUTPUT"
        store.store(record)

        result = orch.compliance_audit.verify_transcripts()
        assert not result.valid
        assert any(
            tampered_window in m["window_id"] or tampered_window in m["detail"]
            for m in result.mismatches
        )
        # The untampered first window still verifies.
        intact = verify_transcripts(
            store,
            orch.compliance_audit,
            session_id=events[0]["session_id"],
        )
        assert intact.checked == 2

    def test_missing_transcript_flagged(self, tmp_path):
        orch = _make_orch(tmp_path, audit_capture_transcripts=True)
        orch.dispatch("system", "task")
        store = orch.compliance_audit.transcript_store
        events = _entries(orch, ComplianceEventType.TRANSCRIPT_RECORDED)
        (tmp_path / "transcripts" / f"{events[0]['data']['raw_output_id']}.json").unlink()
        result = orch.compliance_audit.verify_transcripts()
        assert not result.valid
        assert result.missing == [events[0]["data"]["window_id"]]


# ---------------------------------------------------------------------------
# Redaction
# ---------------------------------------------------------------------------


class TestRedaction:
    def test_redaction_applied_and_recorded(self, tmp_path):
        orch = _make_orch(
            tmp_path,
            audit_capture_transcripts=True,
            audit_transcript_redact_pii=True,
            provider=_PIIProvider(),
        )
        orch.dispatch("system", "task")
        events = _entries(orch, ComplianceEventType.TRANSCRIPT_RECORDED)
        assert len(events) == 1
        data = events[0]["data"]
        assert data["redacted"] is True
        assert "email" in data["pii_types"]
        assert any(p.startswith("phone") for p in data["pii_types"])

        store = orch.compliance_audit.transcript_store
        record = store.get(data["raw_output_id"])
        assert "john@example.com" not in record.output
        assert "[REDACTED:email]" in record.output
        assert any(
            m.startswith("[REDACTED:phone") for m in record.output.split()
        )

    def test_redacted_transcript_skips_chain_hash_check(self, tmp_path):
        """Redacted stored content intentionally differs from chain hashes."""
        orch = _make_orch(
            tmp_path,
            audit_capture_transcripts=True,
            audit_transcript_redact_pii=True,
            provider=_PIIProvider(),
        )
        orch.dispatch("system", "task")
        result = orch.compliance_audit.verify_transcripts()
        assert result.valid, result.mismatches

    def test_redact_text_helper(self):
        scanner = PIIScanner()
        scan = scanner.scan("mail john@example.com today")
        assert redact_text("mail john@example.com today", scan) == "mail [REDACTED:email] today"
        clean = scanner.scan("nothing here")
        assert redact_text("nothing here", clean) == "nothing here"


# ---------------------------------------------------------------------------
# Size cap
# ---------------------------------------------------------------------------


class TestSizeCap:
    def test_oversized_output_truncated(self, tmp_path):
        big = "word " * 5000  # ~25KB output
        orch = _make_orch(
            tmp_path,
            audit_capture_transcripts=True,
            audit_transcript_max_bytes=4096,
            provider=_FakeProvider(output=big),
        )
        orch.dispatch("system", "task")
        events = _entries(orch, ComplianceEventType.TRANSCRIPT_RECORDED)
        assert events[0]["data"]["truncated"] is True

        store = orch.compliance_audit.transcript_store
        record = store.get(events[0]["data"]["raw_output_id"])
        assert record.truncated is True
        assert len(record.output) < len(big)
        # Full-content hash survives truncation for chain linkage.
        assert record.output_sha256 == hash_text(big)
        # Verification uses the stored-output hash and stays green.
        result = orch.compliance_audit.verify_transcripts()
        assert result.valid, result.mismatches

    def test_stored_file_respects_cap(self, tmp_path):
        big = "word " * 5000
        orch = _make_orch(
            tmp_path,
            audit_capture_transcripts=True,
            audit_transcript_max_bytes=4096,
            provider=_FakeProvider(output=big),
        )
        orch.dispatch("system", "task")
        events = _entries(orch, ComplianceEventType.TRANSCRIPT_RECORDED)
        path = tmp_path / "transcripts" / f"{events[0]['data']['raw_output_id']}.json"
        # U-C2: the cap is enforced on the FINAL serialized size — the stored
        # file must never exceed it (no 2× "soft bound").
        assert path.stat().st_size <= 4096
        assert events[0]["data"]["stored_bytes"] <= 4096


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------


class TestExport:
    def test_export_jsonl_includes_transcripts(self, tmp_path):
        orch = _make_orch(tmp_path, audit_capture_transcripts=True)
        orch.dispatch("system", "task")
        plain = orch.compliance_audit.export_jsonl()
        bundle = orch.compliance_audit.export_jsonl(include_transcripts=True)
        assert len(bundle.splitlines()) == len(plain.splitlines()) + 1
        lines = [json.loads(line) for line in bundle.splitlines()]
        transcripts = [ln for ln in lines if ln.get("record_type") == "transcript"]
        assert len(transcripts) == 1
        assert transcripts[0]["output"] == "fake output response"
        assert transcripts[0]["schema_version"] == TRANSCRIPT_SCHEMA_VERSION

    def test_export_jsonl_without_store_unchanged(self):
        orch = _make_orch()
        orch.dispatch("system", "task")
        bundle = orch.compliance_audit.export_jsonl(include_transcripts=True)
        assert all(
            json.loads(line).get("record_type") != "transcript"
            for line in bundle.splitlines()
        )

    def test_export_ocsf_includes_transcript_refs(self, tmp_path):
        orch = _make_orch(tmp_path, audit_capture_transcripts=True)
        orch.dispatch("system", "task")
        plain = orch.compliance_audit.export_ocsf()
        rich = orch.compliance_audit.export_ocsf(include_transcripts=True)
        assert len(plain) == len(rich)
        tx_records = [
            r for r in rich
            if r["metadata"]["event_code"] == ComplianceEventType.TRANSCRIPT_RECORDED.value
        ]
        assert len(tx_records) == 1
        assert tx_records[0]["unmapped"]["crp_transcript_output_sha256"]
        assert tx_records[0]["unmapped"]["crp_transcript_bytes_out"] > 0


# ---------------------------------------------------------------------------
# Schema version 2.1.0
# ---------------------------------------------------------------------------


class TestSchemaVersion:
    def test_transcript_entries_stamped_2_1_0(self, tmp_path):
        orch = _make_orch(tmp_path, audit_capture_transcripts=True)
        orch.dispatch("system", "task")
        export = orch.compliance_audit.export()
        for entry in export["entries"]:
            if entry["event_type"] == ComplianceEventType.TRANSCRIPT_RECORDED.value:
                assert entry["schema_version"] == "2.1.0"
            else:
                assert entry["schema_version"] == "1.0.0"

    def test_schema_version_constant(self):
        assert TRANSCRIPT_SCHEMA_VERSION == "2.1.0"


# ---------------------------------------------------------------------------
# Store unit behaviour
# ---------------------------------------------------------------------------


class TestTranscriptStoreUnit:
    def test_store_roundtrip(self, tmp_path):
        store = TranscriptStore(tmp_path / "t")
        rec = TranscriptRecord(
            raw_output_id="abc-123",
            window_id="w1",
            session_id="s1",
            operation="dispatch",
            system_prompt="sys",
            task_input="task",
            messages=[{"role": "user", "content": "task"}],
            output="out",
        )
        ref = store.store(rec)
        assert ref.endswith("abc-123.json")
        loaded = store.get("abc-123")
        assert loaded.output == "out"
        assert loaded.output_sha256 == hash_text("out")
        assert store.verify_entry(loaded) == []
        assert store.list_ids() == ["abc-123"]

    def test_manifest_written(self, tmp_path):
        store = TranscriptStore(tmp_path / "t")
        rec = TranscriptRecord(
            raw_output_id="x1", window_id="w", session_id="s",
            operation="dispatch", output="o",
        )
        store.store(rec)
        manifest = (tmp_path / "t" / "manifest.jsonl").read_text()
        assert json.loads(manifest.splitlines()[0])["raw_output_id"] == "x1"


# ---------------------------------------------------------------------------
# INCIDENT_* event types + payload shapes
# ---------------------------------------------------------------------------


class TestIncidentEvents:
    def test_enum_values(self):
        assert ComplianceEventType.INCIDENT_CAPTURED.value == "compliance.incident_captured"
        assert ComplianceEventType.INCIDENT_DIAGNOSED.value == "compliance.incident_diagnosed"
        assert (
            ComplianceEventType.INCIDENT_REMEDIATED.value == "compliance.incident_remediated"
        )
        assert ComplianceEventType.INCIDENT_VERIFIED.value == "compliance.incident_verified"
        # str-valued enum — open-extensible for custom incident classes.
        assert isinstance(ComplianceEventType.INCIDENT_CAPTURED.value, str)

    def test_shapes_documented_for_all_four(self):
        assert set(INCIDENT_PAYLOAD_SHAPES) == {
            ComplianceEventType.INCIDENT_CAPTURED.value,
            ComplianceEventType.INCIDENT_DIAGNOSED.value,
            ComplianceEventType.INCIDENT_REMEDIATED.value,
            ComplianceEventType.INCIDENT_VERIFIED.value,
        }

    def test_captured_payload_shape(self):
        good = {
            "incident_id": "inc-1",
            "session_id": "sess-1",
            "component": "nmap_ports",
            "classification": "tool_failure",
            "evidence_refs": ["sha256:aa"],
        }
        assert validate_incident_payload(ComplianceEventType.INCIDENT_CAPTURED, good) == []
        problems = validate_incident_payload(
            ComplianceEventType.INCIDENT_CAPTURED, {**good, "evidence_refs": "not-a-list"}
        )
        assert any("evidence_refs" in p for p in problems)
        problems = validate_incident_payload(ComplianceEventType.INCIDENT_CAPTURED, {})
        assert len(problems) == len(
            INCIDENT_PAYLOAD_SHAPES[ComplianceEventType.INCIDENT_CAPTURED.value]
        )
        assert all(p.startswith("missing field: ") for p in problems)

    def test_diagnosed_payload_shape(self):
        good = {
            "incident_id": "inc-1",
            "session_id": "sess-1",
            "component": "nmap_ports",
            "hypothesis": "VM SSH transport dropped during scan",
            "evidence_refs": ["sha256:bb"],
        }
        assert validate_incident_payload(ComplianceEventType.INCIDENT_DIAGNOSED, good) == []
        problems = validate_incident_payload(
            ComplianceEventType.INCIDENT_DIAGNOSED, {k: v for k, v in good.items() if k != "hypothesis"}
        )
        assert problems == ["missing field: hypothesis"]

    def test_remediated_payload_shape(self):
        good = {
            "incident_id": "inc-1",
            "session_id": "sess-1",
            "action": "restart_service",
            "state_before": {"ssh_reachable": False},
            "state_after": {"ssh_reachable": True},
        }
        assert validate_incident_payload(ComplianceEventType.INCIDENT_REMEDIATED, good) == []
        problems = validate_incident_payload(
            ComplianceEventType.INCIDENT_REMEDIATED, {**good, "action": 42}
        )
        assert any("action" in p for p in problems)

    def test_verified_payload_shape(self):
        good = {
            "incident_id": "inc-1",
            "session_id": "sess-1",
            "probe_result": {"probe": "ssh_banner", "passed": True},
        }
        assert validate_incident_payload(ComplianceEventType.INCIDENT_VERIFIED, good) == []
        problems = validate_incident_payload(ComplianceEventType.INCIDENT_VERIFIED, good)
        assert problems == []

    def test_non_incident_types_unconstrained(self):
        assert validate_incident_payload(ComplianceEventType.DATA_INGESTED, {}) == []

    def test_incident_events_record_in_trail(self):
        trail = ComplianceAuditTrail(session_id="sess-1")
        entry = trail.record(
            ComplianceEventType.INCIDENT_CAPTURED,
            session_id="sess-1",
            data={
                "incident_id": "inc-1",
                "session_id": "sess-1",
                "component": "nmap_ports",
                "classification": "tool_failure",
                "evidence_refs": ["sha256:aa"],
            },
        )
        assert entry.event_type == "compliance.incident_captured"
        valid, broken = trail.verify_chain()
        assert valid and broken == -1


# ---------------------------------------------------------------------------
# Quarantine counters (§7.8)
# ---------------------------------------------------------------------------


class TestQuarantineCounters:
    def test_quarantine_validated_event_recorded(self, tmp_path):
        orch = _make_orch(tmp_path)
        # Ingest untrusted facts → quarantined with 0.7x penalty (§7.8)
        orch.ingest(
            "the fake output response contains useful information",
            source_label="untrusted",
        )
        orch.dispatch("system", "task")
        events = _entries(orch, ComplianceEventType.QUARANTINE_VALIDATED)
        assert len(events) == 1
        data = events[0]["data"]
        assert data["total_quarantined"] >= 1
        assert data["promoted"] + data["rejected"] == data["total_quarantined"]
        # batch_poisoned must reflect the >30% rejection threshold exactly.
        reject_ratio = data["rejected"] / data["total_quarantined"]
        assert data["batch_poisoned"] == (reject_ratio > 0.30)
        assert data["window_id"]

    def test_no_event_when_quarantine_empty(self, tmp_path):
        orch = _make_orch(tmp_path)
        orch.dispatch("system", "task")
        assert _entries(orch, ComplianceEventType.QUARANTINE_VALIDATED) == []

    def test_batch_poisoning_recorded_as_threat(self):
        orch = _make_orch(None)
        orch.ingest("untrusted fact alpha", source_label="poison-src")
        # Poison the batch: nothing cross-references → 100% rejection.
        report = orch._quarantine.validate_and_promote("other-window", {})
        assert report.batch_poisoned
        orch._audit_quarantine_validation(report, window_id="other-window", operation="test")
        threats = _entries(orch, ComplianceEventType.SECURITY_THREAT_DETECTED)
        assert any(t["data"].get("threat_type") == "batch_poisoning" for t in threats)
        qv = _entries(orch, ComplianceEventType.QUARANTINE_VALIDATED)
        assert qv[0]["data"]["batch_poisoned"] is True
