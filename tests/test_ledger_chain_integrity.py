# Copyright © 2025-2026 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Regression tests for the manifest-ledger integrity promises (§7.14.5).

Covers audit findings U-C4 (hash chain silently forks across process
restarts — record() must fold the durable chain head in) and U-C5 (the
chain was unkeyed SHA-256 over public fields, rewritable by anyone with
file access — the chain is now HMAC-keyed via KeyProvider, fail closed on
verification, with external anchoring making tail truncation detectable).
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from crp import (
    ContextManifest,
    ContextSource,
    EnvVarKeyProvider,
    KeyProvider,
    LedgerChainError,
    ManifestLedger,
    ManifestLedgerEntry,
    RotatingKeyProvider,
    SourceKind,
    TrustLevel,
)
from crp.core.manifest_ledger import _compute_entry_hash

SECRET = b"k" * 32
SECRET2 = b"z" * 32


def _manifest(source_id: str = "vdb-main") -> ContextManifest:
    m = ContextManifest(system_id="test")
    m.add(
        ContextSource(
            kind=SourceKind.VECTOR_DB,
            source_id=source_id,
            trust_level=TrustLevel.TRUSTED,
        )
    )
    return m


class _StaticKeyProvider(KeyProvider):
    """Test-only provider with a fixed key."""

    def __init__(self, key: bytes) -> None:
        self._key = key

    def current(self) -> bytes:
        return self._key

    def candidates(self):
        yield self._key


# ---------------------------------------------------------------------------
# U-C4 — restart must not fork the chain
# ---------------------------------------------------------------------------


class TestRestartForkFix:
    def test_record_without_load_chains_onto_disk_head(self, tmp_path: Path) -> None:
        """Regression for U-C4: a fresh process that records without calling
        load() must append onto the durable chain head, not write a second
        genesis entry."""
        first = ManifestLedger(session_dir=tmp_path)
        e1 = first.record("sess", _manifest())
        # Brand-new instance, cold cache — the old code wrote a second
        # genesis entry (turn=1, prev_hash="") here.
        second = ManifestLedger(session_dir=tmp_path)
        e2 = second.record("sess", _manifest(source_id="other"))
        assert e2.turn == 2
        assert e2.prev_hash == e1.entry_hash

    def test_chain_verifies_across_instances(self, tmp_path: Path) -> None:
        first = ManifestLedger(session_dir=tmp_path)
        first.record("sess", _manifest())
        second = ManifestLedger(session_dir=tmp_path)
        second.record("sess", _manifest(source_id="b"))
        third = ManifestLedger(session_dir=tmp_path)
        assert third.verify_chain("sess") == []
        entries = third.load("sess")
        assert [e.turn for e in entries] == [1, 2]

    def test_three_record_only_processes_no_fork(self, tmp_path: Path) -> None:
        """The empirical U-C4 reproduction: three independent record-only
        'processes' used to leave [(1,'',h1),(1,'',h2)] on disk."""
        for i in range(3):
            ledger = ManifestLedger(session_dir=tmp_path)
            ledger.record("sess", _manifest(source_id=f"s{i}"))
        final = ManifestLedger(session_dir=tmp_path)
        entries = final.load("sess")
        assert [e.turn for e in entries] == [1, 2, 3]
        assert final.verify_chain("sess") == []

    def test_duplicate_genesis_raises_on_load(self, tmp_path: Path) -> None:
        """A ledger file that already contains a fork (two chained genesis
        entries) must surface as LedgerChainError, not chain silently."""
        path = tmp_path / "forked.manifest.jsonl"
        m = _manifest()
        now = time.time()
        g1 = ManifestLedgerEntry("forked", 1, now, m, "", _compute_entry_hash("forked", 1, now, m._canonical_payload(), ""))
        g2 = ManifestLedgerEntry("forked", 1, now + 1, m, "", _compute_entry_hash("forked", 1, now + 1, m._canonical_payload(), ""))
        path.write_text(g1.to_jsonl() + "\n" + g2.to_jsonl() + "\n", encoding="utf-8")
        ledger = ManifestLedger(session_dir=tmp_path)
        with pytest.raises(LedgerChainError):
            ledger.load("forked")

    def test_duplicate_genesis_raises_on_record(self, tmp_path: Path) -> None:
        """record() must refuse to extend an already-forked ledger."""
        path = tmp_path / "forked.manifest.jsonl"
        m = _manifest()
        now = time.time()
        g1 = ManifestLedgerEntry("forked", 1, now, m, "", _compute_entry_hash("forked", 1, now, m._canonical_payload(), ""))
        g2 = ManifestLedgerEntry("forked", 1, now + 1, m, "", _compute_entry_hash("forked", 1, now + 1, m._canonical_payload(), ""))
        path.write_text(g1.to_jsonl() + "\n" + g2.to_jsonl() + "\n", encoding="utf-8")
        ledger = ManifestLedger(session_dir=tmp_path)
        with pytest.raises(LedgerChainError):
            ledger.record("forked", _manifest())

    def test_legacy_entries_without_hashes_not_flagged_as_fork(self, tmp_path: Path) -> None:
        """Pre-2.3 rows (entry_hash="") must keep loading without a fork error."""
        m = _manifest()
        entry = ManifestLedgerEntry("old", 1, time.time(), m)
        (tmp_path / "old.manifest.jsonl").write_text(entry.to_jsonl() + "\n", encoding="utf-8")
        ledger = ManifestLedger(session_dir=tmp_path)
        assert len(ledger.load("old")) == 1


# ---------------------------------------------------------------------------
# U-C5 — keyed chain: tamper-evidence that survives file access
# ---------------------------------------------------------------------------


class TestKeyedChain:
    def test_verify_clean_keyed_chain(self, tmp_path: Path) -> None:
        ledger = ManifestLedger(
            session_dir=tmp_path, chain_key_provider=_StaticKeyProvider(SECRET)
        )
        ledger.record("s", _manifest())
        ledger.record("s", _manifest(source_id="b"))
        assert ledger.verify_chain("s") == []

    def test_forgery_with_public_algorithm_detected(self, tmp_path: Path) -> None:
        """The U-C5 attack: rewrite history and recompute the chain with the
        public (unkeyed) algorithm. Unkeyed ledger: undetected (documented
        legacy weakness). Keyed ledger: every forged entry is flagged."""
        # Keyed ledger, then a full honest recompute of the file using only
        # the public algorithm — exactly what a file-access attacker can do.
        keyed = ManifestLedger(
            session_dir=tmp_path / "keyed", chain_key_provider=_StaticKeyProvider(SECRET)
        )
        keyed.record("s", _manifest())
        keyed.record("s", _manifest(source_id="b"))
        forged_lines = []
        prev = ""
        for i, line in enumerate(
            (tmp_path / "keyed" / "s.manifest.jsonl").read_text().splitlines(), 1
        ):
            data = json.loads(line)
            canonical = json.dumps(
                data["manifest"], separators=(",", ":"), sort_keys=True
            ).encode()
            # Tamper: flip the recorded turn.
            data["turn"] = 100 + i
            data["prev_hash"] = prev
            data["entry_hash"] = _compute_entry_hash(
                data["session_id"], data["turn"], data["recorded_at"],
                _canonical(data["manifest"]), prev,
            )
            prev = data["entry_hash"]
            forged_lines.append(json.dumps(data, separators=(",", ":")))
        (tmp_path / "keyed" / "s.manifest.jsonl").write_text(
            "\n".join(forged_lines) + "\n", encoding="utf-8"
        )
        keyed.clear_cache("s")  # drop the record-time cache; re-read disk
        broken = keyed.verify_chain("s")
        assert broken, "keyed chain must flag an unkeyed recomputation"

    def test_keyed_chain_fails_closed_on_unkeyed_entries(self, tmp_path: Path) -> None:
        """With a provider configured, legacy unkeyed entries are flagged."""
        unkeyed = ManifestLedger(session_dir=tmp_path)
        unkeyed.record("s", _manifest())
        keyed_reader = ManifestLedger(
            session_dir=tmp_path, chain_key_provider=_StaticKeyProvider(SECRET)
        )
        broken = keyed_reader.verify_chain("s")
        assert broken and all(reason == "entry_hash_mismatch" for _, reason in broken)

    def test_wrong_key_flags_entries(self, tmp_path: Path) -> None:
        ledger = ManifestLedger(
            session_dir=tmp_path, chain_key_provider=_StaticKeyProvider(SECRET)
        )
        ledger.record("s", _manifest())
        reader = ManifestLedger(
            session_dir=tmp_path, chain_key_provider=_StaticKeyProvider(SECRET2)
        )
        broken = reader.verify_chain("s")
        assert len(broken) == 1

    def test_rotation_grace_via_candidates(self, tmp_path: Path) -> None:
        """Entries written under the retired key still verify during grace."""
        rotating = RotatingKeyProvider(initial=SECRET)
        ledger = ManifestLedger(session_dir=tmp_path, chain_key_provider=rotating)
        ledger.record("s", _manifest())
        rotating.rotate(SECRET2)
        ledger.record("s", _manifest(source_id="b"))
        assert ledger.verify_chain("s") == []
        # After retire_all the old entry is flagged again.
        rotating.retire_all()
        broken = ledger.verify_chain("s")
        assert [t for t, _ in broken] == [1]

    def test_env_var_enables_keying(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CRP_MANIFEST_SECRET", "envsecret!-" + "x" * 40)
        ledger = ManifestLedger(session_dir=tmp_path)
        ledger.record("s", _manifest())
        # A keyed verifier (env-derived) accepts it...
        assert ledger.verify_chain("s") == []
        # ...and an explicit provider with a different key flags it.
        other = ManifestLedger(
            session_dir=tmp_path, chain_key_provider=_StaticKeyProvider(SECRET)
        )
        assert other.verify_chain("s") != []


def _canonical(manifest_dict: dict) -> bytes:
    """Canonical manifest payload identical to ContextManifest._canonical_payload."""
    from crp import ContextManifest

    return ContextManifest.from_json(json.dumps(manifest_dict))._canonical_payload()


# ---------------------------------------------------------------------------
# U-C5 — anchoring: tail truncation detection
# ---------------------------------------------------------------------------


class TestAnchoring:
    def test_anchor_and_verify(self, tmp_path: Path) -> None:
        ledger = ManifestLedger(
            session_dir=tmp_path / "ledgers",
            chain_key_provider=_StaticKeyProvider(SECRET),
        )
        ledger.record("s", _manifest())
        ledger.record("s", _manifest(source_id="b"))
        ledger.record("s", _manifest(source_id="c"))
        anchor_path = tmp_path / "anchor.json"
        ledger.anchor("s", anchor_path)
        assert ledger.verify_anchored("s", anchor_path)

    def test_tail_truncation_detected(self, tmp_path: Path) -> None:
        """Delete the last N lines after anchoring → verification fails."""
        ledger = ManifestLedger(
            session_dir=tmp_path / "ledgers",
            chain_key_provider=_StaticKeyProvider(SECRET),
        )
        for i in range(4):
            ledger.record("s", _manifest(source_id=f"x{i}"))
        anchor_path = tmp_path / "anchor.json"
        ledger.anchor("s", anchor_path)
        path = tmp_path / "ledgers" / "s.manifest.jsonl"
        lines = path.read_text().splitlines()
        path.write_text("\n".join(lines[:2]) + "\n", encoding="utf-8")
        ledger.clear_cache("s")  # force re-read of the truncated file
        assert not ledger.verify_anchored("s", anchor_path)

    def test_extension_detected(self, tmp_path: Path) -> None:
        """Append entries after anchoring without re-anchoring → fails."""
        ledger = ManifestLedger(
            session_dir=tmp_path / "ledgers",
            chain_key_provider=_StaticKeyProvider(SECRET),
        )
        ledger.record("s", _manifest())
        anchor_path = tmp_path / "anchor.json"
        ledger.anchor("s", anchor_path)
        ledger.record("s", _manifest(source_id="new"))
        assert not ledger.verify_anchored("s", anchor_path)

    def test_entry_tampering_detected(self, tmp_path: Path) -> None:
        ledger = ManifestLedger(
            session_dir=tmp_path / "ledgers",
            chain_key_provider=_StaticKeyProvider(SECRET),
        )
        for i in range(3):
            ledger.record("s", _manifest(source_id=f"x{i}"))
        anchor_path = tmp_path / "anchor.json"
        ledger.anchor("s", anchor_path)
        path = tmp_path / "ledgers" / "s.manifest.jsonl"
        lines = path.read_text().splitlines()
        data = json.loads(lines[1])
        data["recorded_at"] += 1.0  # tamper a hashed field, keep entry_hash
        lines[1] = json.dumps(data, separators=(",", ":"))
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        ledger.clear_cache("s")  # force re-read of the tampered file
        # The keyed chain flags the tamper (recomputed HMAC mismatches)…
        assert ledger.verify_chain("s"), "keyed chain must flag the tampered field"
        # …and the anchor fails too when the tampered entry_hash column is
        # what changed (root over entry_hash values moves).
        data = json.loads(lines[1])
        data["entry_hash"] = "0" * 64
        lines[1] = json.dumps(data, separators=(",", ":"))
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        ledger.clear_cache("s")
        assert not ledger.verify_anchored("s", anchor_path)
