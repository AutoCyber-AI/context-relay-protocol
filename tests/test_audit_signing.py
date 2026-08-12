# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Tests for Ed25519 audit receipts (crp/security/audit_trail.py, audit_v2).

cryptography is an optional dependency: receipt tests skip when it is absent
(the suite's importorskip pattern); the zero-dependency fallback is tested by
hiding the package via ``sys.modules``.
"""

from __future__ import annotations

import sys

import pytest

from crp.security.audit_trail import ActionSigner, ComplianceAuditTrail

crypto = pytest.importorskip("cryptography", reason="receipt tests need [security] extra")


@pytest.fixture()
def signer() -> ActionSigner:
    return ActionSigner()


@pytest.fixture()
def signed_trail(signer: ActionSigner) -> ComplianceAuditTrail:
    trail = ComplianceAuditTrail(action_signer=signer)
    for i in range(4):
        trail.record("compliance.data_processed", session_id="s", data={"i": i})
    return trail


class TestSigner:
    def test_sign_verify_roundtrip(self, signer: ActionSigner) -> None:
        sig = signer.sign("ab" * 32)
        assert ActionSigner.verify(signer.public_key_pem(), "ab" * 32, sig)

    def test_wrong_key_rejected(self, signer: ActionSigner) -> None:
        other = ActionSigner()
        sig = signer.sign("ab" * 32)
        assert not ActionSigner.verify(other.public_key_pem(), "ab" * 32, sig)

    def test_wrong_hash_rejected(self, signer: ActionSigner) -> None:
        sig = signer.sign("ab" * 32)
        assert not ActionSigner.verify(signer.public_key_pem(), "cd" * 32, sig)

    def test_malformed_inputs_return_false(self, signer: ActionSigner) -> None:
        assert not ActionSigner.verify(signer.public_key_pem(), "zz", "aa")
        assert not ActionSigner.verify(b"not a pem", "ab" * 32, "aa")

    def test_ephemeral_keys_are_unique(self) -> None:
        assert ActionSigner().public_key_pem() != ActionSigner().public_key_pem()

    def test_loads_key_from_env_path(
        self, tmp_path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

        key = Ed25519PrivateKey.generate()
        pem = key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        key_path = tmp_path / "audit_signing_key.pem"
        key_path.write_bytes(pem)
        monkeypatch.setenv("CRP_AUDIT_SIGNING_KEY", str(key_path))
        loaded = ActionSigner()
        expected_pub = key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        assert loaded.public_key_pem() == expected_pub


class TestTrailReceipts:
    def test_entries_carry_receipts_and_v2_schema(
        self, signed_trail: ComplianceAuditTrail
    ) -> None:
        for entry in signed_trail.query():
            assert entry.receipt
            assert len(entry.receipt) == 128  # Ed25519 signature hex
            assert entry.schema_version == "2.0.0"
        assert "receipt" in signed_trail.query()[0].to_dict()

    def test_chain_and_receipts_verify(self, signed_trail: ComplianceAuditTrail) -> None:
        assert signed_trail.verify_chain() == (True, -1)
        assert signed_trail.verify_chain(verify_receipts=True) == (True, -1)

    def test_receipts_verify_with_explicit_public_key(
        self, signed_trail: ComplianceAuditTrail, signer: ActionSigner
    ) -> None:
        # A verifier holding only the public key can validate every receipt.
        pub = signer.public_key_pem()
        assert signed_trail.verify_chain(
            verify_receipts=True, public_key_pem=pub
        ) == (True, -1)
        for entry in signed_trail.query():
            assert ActionSigner.verify(pub, entry.entry_hash, entry.receipt)

    def test_verify_receipts_with_wrong_key_fails(
        self, signed_trail: ComplianceAuditTrail
    ) -> None:
        wrong = ActionSigner()
        valid, broken_at = signed_trail.verify_chain(
            verify_receipts=True, public_key_pem=wrong.public_key_pem()
        )
        assert not valid and broken_at == 0

    def test_tampered_receipt_detected(self, signed_trail: ComplianceAuditTrail) -> None:
        entry = signed_trail.query()[1]
        entry.receipt = ("0" if entry.receipt[0] != "0" else "1") + entry.receipt[1:]
        valid, broken_at = signed_trail.verify_chain(verify_receipts=True)
        assert not valid and broken_at == 1

    def test_missing_receipt_fails_closed(self, signer: ActionSigner) -> None:
        trail = ComplianceAuditTrail(action_signer=signer)
        trail.record("compliance.data_accessed", session_id="s")
        trail._entries[0].receipt = ""
        valid, _ = trail.verify_chain(verify_receipts=True)
        assert not valid

    def test_verify_receipts_without_key_raises(self) -> None:
        trail = ComplianceAuditTrail()
        trail.record("compliance.data_accessed", session_id="s")
        with pytest.raises(ValueError, match="public_key_pem"):
            trail.verify_chain(verify_receipts=True)


class TestZeroDependencyMode:
    def test_trail_without_signer_unchanged(self) -> None:
        trail = ComplianceAuditTrail()
        trail.record("compliance.data_accessed", session_id="s")
        entry = trail.query()[0]
        assert entry.receipt == ""
        assert entry.schema_version == "1.0.0"
        assert trail.verify_chain() == (True, -1)

    def test_signer_raises_friendly_importerror_when_crypto_missing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # ``from x.y import z`` consults sys.modules["x.y"] first, so the
        # exact submodules imported by _require_ed25519 must be hidden too.
        for mod in (
            "cryptography",
            "cryptography.hazmat",
            "cryptography.hazmat.primitives",
            "cryptography.hazmat.primitives.serialization",
            "cryptography.hazmat.primitives.asymmetric",
            "cryptography.hazmat.primitives.asymmetric.ed25519",
        ):
            monkeypatch.setitem(sys.modules, mod, None)
        with pytest.raises(ImportError, match="crprotocol\\[security\\]"):
            ActionSigner()

    def test_export_omits_receipt_when_signatures_excluded(
        self, signed_trail: ComplianceAuditTrail
    ) -> None:
        export = signed_trail.export(include_signatures=False)
        for entry in export["entries"]:
            assert "receipt" not in entry
            assert "signature" not in entry
