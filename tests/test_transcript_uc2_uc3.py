# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""U-C2 / U-C3 regression tests — transcript byte cap and PII redaction (§7.14).

U-C2: the per-transcript byte cap must be enforced on the FINAL serialized
record size (encode-then-measure), never on a single field with a chars-based
budget; stored files must never exceed the cap.

U-C3: PII redaction defaults ON whenever capture is enabled, and it must
cover the full stored message array — including envelope facts pulled in
from warm-store/CKF — not just the top-level system_prompt/task_input/output
fields.  Residual recall limits are documented on the event.
"""

from __future__ import annotations

import json

from crp.core.orchestrator import CRPOrchestrator
from crp.providers.base import LLMProvider
from crp.security.audit_trail import ComplianceEventType
from crp.security.transcript_store import TranscriptRecord, TranscriptStore, hash_text

# ---------------------------------------------------------------------------
# Helpers
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
        return "fake-uc2uc3-v1"


def _make_orch(tmp_path, **kwargs) -> CRPOrchestrator:
    provider = kwargs.pop("provider", None) or _FakeProvider()
    if "max_continuations" not in kwargs:
        kwargs["max_continuations"] = 0
    if "audit_transcript_dir" not in kwargs:
        kwargs["audit_transcript_dir"] = str(tmp_path / "transcripts")
    return CRPOrchestrator(provider=provider, **kwargs)


def _record(**kwargs) -> TranscriptRecord:
    kwargs.setdefault("raw_output_id", "rid-uc2")
    kwargs.setdefault("window_id", "wid-uc2")
    kwargs.setdefault("session_id", "sid-uc2")
    kwargs.setdefault("operation", "dispatch")
    return TranscriptRecord(**kwargs)


def _file_bytes(store: TranscriptStore, raw_output_id: str) -> bytes:
    path = store._path_for(raw_output_id)
    assert path is not None
    return path.read_bytes()


# ---------------------------------------------------------------------------
# U-C2 — byte cap enforced on the final serialized size
# ---------------------------------------------------------------------------


class TestUc2ByteCap:
    def test_random_field_sizes_never_exceed_cap(self, tmp_path):
        """Field sizes in [0, 4×cap]: the stored file is always ≤ cap."""
        cap = 4096
        for size in (0, 1, 512, 2048, 4096, 8192, 16384):
            store = TranscriptStore(tmp_path / f"s{size}", max_bytes=cap)
            filler = "abcdefgh" * (size // 8 + 1)
            record = _record(
                system_prompt=filler[:size],
                task_input=filler[:size],
                output=filler[:size],
                messages=[
                    {"role": "system", "content": filler[:size]},
                    {"role": "user", "content": filler[:size]},
                ],
            )
            store.store(record)
            assert len(_file_bytes(store, record.raw_output_id)) <= cap, (
                f"stored file exceeds cap for field size {size}"
            )
            if size and record.truncated:
                assert record.stored_bytes <= cap

    def test_audit_repro_20k_messages_20k_output(self, tmp_path):
        """The audit's empirical repro: 20 KB messages + 20 KB output, cap 4096."""
        store = TranscriptStore(tmp_path, max_bytes=4096)
        big = "word " * 4000  # 20 KB
        record = _record(
            system_prompt="sys",
            task_input="task",
            output=big,
            messages=[{"role": "user", "content": big}],
        )
        store.store(record)
        stored = _file_bytes(store, record.raw_output_id)
        assert len(stored) <= 4096, f"stored {len(stored)} bytes, cap is 4096"
        assert record.truncated is True

    def test_multibyte_utf8_never_split_and_cap_holds(self, tmp_path):
        """Chars-based truncation overshoots on multi-byte UTF-8; bytes don't."""
        store = TranscriptStore(tmp_path, max_bytes=4096)
        euro = "€" * 6000  # 3 bytes per char → 18 KB
        record = _record(output=euro, messages=[{"role": "user", "content": euro}])
        store.store(record)
        stored = _file_bytes(store, record.raw_output_id)
        assert len(stored) <= 4096
        # Stored JSON is still valid and parseable (no split chars).
        data = json.loads(stored.decode("utf-8"))
        assert data["truncated"] is True

    def test_truncated_record_still_verifies(self, tmp_path):
        """Stored-content hashes cover the truncated content: verify_entry is green."""
        store = TranscriptStore(tmp_path, max_bytes=2048)
        big = "x" * 20_000
        record = _record(output=big, messages=[{"role": "user", "content": big}])
        store.store(record)
        loaded = store.get(record.raw_output_id)
        assert loaded is not None
        assert store.verify_entry(loaded) == []

    def test_full_output_hash_kept_for_chain_linkage(self, tmp_path):
        """output_sha256 covers the FULL pre-truncation output (chain survives)."""
        store = TranscriptStore(tmp_path, max_bytes=2048)
        big = "chain me " * 5000
        record = _record(output=big)
        store.store(record)
        assert record.output_sha256 == hash_text(big)
        assert record.stored_output_sha256 != record.output_sha256

    def test_undersized_record_untouched(self, tmp_path):
        store = TranscriptStore(tmp_path, max_bytes=4096)
        record = _record(
            output="small", messages=[{"role": "user", "content": "task"}]
        )
        store.store(record)
        assert record.truncated is False
        loaded = store.get(record.raw_output_id)
        assert loaded is not None and loaded.output == "small"


# ---------------------------------------------------------------------------
# U-C3 — PII redaction default-on and covers the messages array
# ---------------------------------------------------------------------------


class TestUc3Redaction:
    _FACT_PII = "jane@example.com"
    _TASK_PII = "john@example.com"

    def _dispatch_with_fact(self, tmp_path, **kwargs) -> tuple[CRPOrchestrator, str]:
        orch = _make_orch(
            tmp_path, audit_capture_transcripts=True, **kwargs
        )
        orch.ingest(f"Contact {self._FACT_PII} for the domain transfer records.")
        orch.dispatch(
            f"You are an analyst. Report to {self._TASK_PII}.",
            "Summarise the contact details.",
        )
        store = orch.compliance_audit.transcript_store
        events = [
            e
            for e in orch.compliance_audit.export()["entries"]
            if e["event_type"] == ComplianceEventType.TRANSCRIPT_RECORDED.value
        ]
        assert events, "expected a TRANSCRIPT_RECORDED event"
        return orch, events[0]["data"]["raw_output_id"]

    def test_redaction_defaults_on_when_capture_on(self, tmp_path):
        orch, raw_output_id = self._dispatch_with_fact(tmp_path)
        store = orch.compliance_audit.transcript_store
        record = store.get(raw_output_id)
        assert record is not None
        assert record.redacted is True
        events = [
            e
            for e in orch.compliance_audit.export()["entries"]
            if e["event_type"] == ComplianceEventType.TRANSCRIPT_RECORDED.value
        ]
        data = events[0]["data"]
        assert data["redacted"] is True
        assert data["pii_recall"] == "scanner-limited"
        assert "email" in data["pii_types"]

    def test_no_raw_pii_anywhere_in_stored_json(self, tmp_path):
        """PII in task input AND in an ingested fact (envelope → messages):
        no raw PII substring anywhere in the stored JSON, by default."""
        orch, raw_output_id = self._dispatch_with_fact(tmp_path)
        store = orch.compliance_audit.transcript_store
        raw = _file_bytes(store, raw_output_id).decode("utf-8")
        assert self._TASK_PII not in raw
        assert self._FACT_PII not in raw
        assert "[REDACTED:email]" in raw

    def test_opt_out_still_stores_raw(self, tmp_path):
        """Explicit audit_transcript_redact_pii=False opts out (raw path kept)."""
        orch, raw_output_id = self._dispatch_with_fact(
            tmp_path, audit_transcript_redact_pii=False
        )
        store = orch.compliance_audit.transcript_store
        record = store.get(raw_output_id)
        assert record is not None
        assert record.redacted is False

    def test_env_var_opt_out(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CRP_AUDIT_CAPTURE_TRANSCRIPTS", "true")
        monkeypatch.setenv("CRP_AUDIT_TRANSCRIPT_DIR", str(tmp_path / "envtx"))
        monkeypatch.setenv("CRP_AUDIT_TRANSCRIPT_REDACT_PII", "false")
        orch = CRPOrchestrator(provider=_FakeProvider(), max_continuations=0)
        orch.dispatch("system", "task")
        events = [
            e
            for e in orch.compliance_audit.export()["entries"]
            if e["event_type"] == ComplianceEventType.TRANSCRIPT_RECORDED.value
        ]
        assert events and events[0]["data"]["redacted"] is False

    def test_pii_reaches_messages_proving_the_leak_vector(self, tmp_path):
        """Control: with redaction off, the ingested fact's PII IS persisted
        in the stored transcript (proves the messages array was the leak)."""
        orch, raw_output_id = self._dispatch_with_fact(
            tmp_path, audit_transcript_redact_pii=False
        )
        store = orch.compliance_audit.transcript_store
        raw = _file_bytes(store, raw_output_id).decode("utf-8")
        assert self._FACT_PII in raw
