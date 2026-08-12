# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Tests for external audit anchoring (crp/security/audit_anchor.py).

Covers anchor roundtrip, tamper/mismatch detection (appended entries, edited
anchor file, corrupted file), signed vs unsigned records, and the pluggable
transport interface. cryptography is present in the main venv; the unsigned
path is exercised by forcing the signer away.
"""

from __future__ import annotations

import json
from datetime import datetime

import pytest

from crp.security import audit_anchor as anchor_mod
from crp.security.audit_anchor import (
    AnchorRecord,
    AnchorTransport,
    anchor_to_file,
    anchor_trail,
    verify_anchor,
)
from crp.security.audit_trail import ComplianceAuditTrail


@pytest.fixture()
def trail() -> ComplianceAuditTrail:
    t = ComplianceAuditTrail()
    for i in range(5):
        t.record("compliance.data_accessed", session_id="s", data={"i": i})
    return t


class InMemoryTransport(AnchorTransport):
    """Stand-in for a future TSA HTTP transport (RFC 3161 client)."""

    def __init__(self) -> None:
        self.record: AnchorRecord | None = None

    def write(self, record: AnchorRecord) -> None:
        self.record = record

    def read(self) -> AnchorRecord:
        if self.record is None:
            raise ValueError("no anchor stored")
        return self.record


class TestAnchorRoundtrip:
    def test_anchor_and_verify(self, trail: ComplianceAuditTrail, tmp_path) -> None:
        path = tmp_path / "anchor.json"
        record = anchor_to_file(trail, path)
        assert record.method == "local-file"
        assert record.entry_count == 5
        assert len(record.root_hash) == 64
        # anchored_at must be a parseable ISO-8601 timestamp
        datetime.fromisoformat(record.anchored_at)
        assert verify_anchor(trail, path)

    def test_signed_when_crypto_available(self, trail: ComplianceAuditTrail, tmp_path) -> None:
        pytest.importorskip("cryptography")
        path = tmp_path / "anchor.json"
        record = anchor_to_file(trail, path)
        assert record.signature and record.signer_public_key
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["signature"] == record.signature

    def test_unsigned_when_signer_unavailable(
        self, trail: ComplianceAuditTrail, tmp_path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def _no_crypto(*args: object, **kwargs: object) -> object:
            raise ImportError("cryptography not installed")

        monkeypatch.setattr(anchor_mod, "ActionSigner", _no_crypto)
        path = tmp_path / "anchor.json"
        record = anchor_to_file(trail, path)
        assert record.signature == ""
        assert verify_anchor(trail, path)  # root/count check still works

    def test_pluggable_transport(self, trail: ComplianceAuditTrail) -> None:
        transport = InMemoryTransport()
        record = anchor_trail(trail, transport)
        assert transport.record is record
        assert record.method == "in-memory"
        assert verify_anchor(trail, "", transport=transport)


class TestMismatchDetection:
    def test_appended_entry_breaks_anchor(
        self, trail: ComplianceAuditTrail, tmp_path
    ) -> None:
        path = tmp_path / "anchor.json"
        anchor_to_file(trail, path)
        trail.record("compliance.data_deleted", session_id="s")
        assert not verify_anchor(trail, path)

    def test_tampered_trail_entry_breaks_anchor(
        self, trail: ComplianceAuditTrail, tmp_path
    ) -> None:
        path = tmp_path / "anchor.json"
        anchor_to_file(trail, path)
        entry = trail.query()[2]
        entry.entry_hash = ("0" if entry.entry_hash[0] != "0" else "1") + entry.entry_hash[1:]
        assert not verify_anchor(trail, path)

    def test_tampered_anchor_file_detected(
        self, trail: ComplianceAuditTrail, tmp_path
    ) -> None:
        pytest.importorskip("cryptography")
        path = tmp_path / "anchor.json"
        anchor_to_file(trail, path)
        data = json.loads(path.read_text(encoding="utf-8"))
        rh = data["root_hash"]
        data["root_hash"] = ("0" if rh[0] != "0" else "1") + rh[1:]
        path.write_text(json.dumps(data), encoding="utf-8")
        assert not verify_anchor(trail, path)

    def test_corrupted_anchor_file_fails_closed(
        self, trail: ComplianceAuditTrail, tmp_path
    ) -> None:
        path = tmp_path / "anchor.json"
        path.write_text("{not json", encoding="utf-8")
        assert not verify_anchor(trail, path)

    def test_missing_anchor_file_fails_closed(
        self, trail: ComplianceAuditTrail, tmp_path
    ) -> None:
        assert not verify_anchor(trail, tmp_path / "no-such-file.json")


class TestAnchorRecord:
    def test_from_dict_roundtrip(self) -> None:
        record = AnchorRecord(
            root_hash="ab" * 32,
            entry_count=7,
            anchored_at="2026-08-02T00:00:00+00:00",
            signature="cd" * 64,
            signer_public_key="-----BEGIN PUBLIC KEY-----\n...",
        )
        assert AnchorRecord.from_dict(record.to_dict()) == record

    def test_from_dict_rejects_malformed(self) -> None:
        with pytest.raises(ValueError, match="malformed anchor record"):
            AnchorRecord.from_dict({"entry_count": "x"})

    def test_tbs_bytes_canonical_and_signature_free(self) -> None:
        kwargs = dict(
            root_hash="ab" * 32, entry_count=3, anchored_at="2026-08-02T00:00:00+00:00"
        )
        signed = AnchorRecord(signature="cd" * 64, **kwargs)
        unsigned = AnchorRecord(**kwargs)
        assert signed.tbs_bytes() == unsigned.tbs_bytes()
