# Copyright © 2025-2026 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Tests for CRP 2.2 manifest ledger & key providers (§7.14.5)."""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from crp import (
    ContextManifest,
    ContextSource,
    EnvVarKeyProvider,
    ManifestLedger,
    ManifestLedgerEntry,
    ManifestValidationError,
    RotatingKeyProvider,
    SourceKind,
    TrustLevel,
)


SECRET = b"a" * 32
SECRET2 = b"b" * 32


def _signed(secret: bytes = SECRET, *, source_id: str = "vdb-main") -> ContextManifest:
    m = ContextManifest(system_id="test")
    m.add(
        ContextSource(
            kind=SourceKind.VECTOR_DB,
            source_id=source_id,
            trust_level=TrustLevel.TRUSTED,
        )
    )
    m.sign(secret)
    return m


# ---------------------------------------------------------------------------
# ManifestLedgerEntry
# ---------------------------------------------------------------------------


class TestManifestLedgerEntry:
    def test_jsonl_round_trip(self) -> None:
        m = _signed()
        entry = ManifestLedgerEntry(
            session_id="s1", turn=1, recorded_at=time.time(), manifest=m
        )
        line = entry.to_jsonl()
        assert "\n" not in line
        rehydrated = ManifestLedgerEntry.from_jsonl(line)
        assert rehydrated.session_id == "s1"
        assert rehydrated.turn == 1
        assert rehydrated.manifest.manifest_id == m.manifest_id
        assert rehydrated.manifest.verify(SECRET)

    def test_from_jsonl_preserves_signature(self) -> None:
        m = _signed()
        entry = ManifestLedgerEntry(
            session_id="s1", turn=1, recorded_at=1.0, manifest=m
        )
        rehydrated = ManifestLedgerEntry.from_jsonl(entry.to_jsonl())
        assert rehydrated.manifest.signature == m.signature


# ---------------------------------------------------------------------------
# ManifestLedger — record / load / history
# ---------------------------------------------------------------------------


class TestManifestLedgerIO:
    def test_record_creates_file_and_appends(self, tmp_path: Path) -> None:
        ledger = ManifestLedger(session_dir=tmp_path)
        m1 = _signed()
        m2 = _signed(source_id="vdb-other")
        e1 = ledger.record("sess-a", m1)
        e2 = ledger.record("sess-a", m2)
        assert e1.turn == 1
        assert e2.turn == 2
        path = tmp_path / "sess-a.manifest.jsonl"
        assert path.exists()
        assert len(path.read_text().strip().splitlines()) == 2

    def test_record_explicit_turn(self, tmp_path: Path) -> None:
        ledger = ManifestLedger(session_dir=tmp_path)
        e = ledger.record("sess-a", _signed(), turn=42)
        assert e.turn == 42

    def test_record_rejects_empty_session(self, tmp_path: Path) -> None:
        ledger = ManifestLedger(session_dir=tmp_path)
        with pytest.raises(ValueError):
            ledger.record("", _signed())

    def test_load_rehydrates_from_disk(self, tmp_path: Path) -> None:
        # Write via one ledger instance
        first = ManifestLedger(session_dir=tmp_path)
        first.record("sess-b", _signed())
        first.record("sess-b", _signed(source_id="vdb-2"))
        # Read via a fresh instance
        second = ManifestLedger(session_dir=tmp_path)
        entries = second.load("sess-b")
        assert len(entries) == 2
        assert entries[0].turn == 1
        assert entries[1].turn == 2

    def test_load_missing_returns_empty(self, tmp_path: Path) -> None:
        ledger = ManifestLedger(session_dir=tmp_path)
        assert ledger.load("nobody") == []

    def test_latest_returns_last(self, tmp_path: Path) -> None:
        ledger = ManifestLedger(session_dir=tmp_path)
        ledger.record("s", _signed(source_id="a"))
        ledger.record("s", _signed(source_id="b"))
        latest = ledger.latest("s")
        assert latest is not None
        assert "b" in latest.manifest.declared_source_ids()

    def test_latest_empty_session(self, tmp_path: Path) -> None:
        ledger = ManifestLedger(session_dir=tmp_path)
        assert ledger.latest("missing") is None

    def test_corrupt_line_raises(self, tmp_path: Path) -> None:
        ledger = ManifestLedger(session_dir=tmp_path)
        (tmp_path / "bad.manifest.jsonl").write_text("not-json\n")
        with pytest.raises(ManifestValidationError):
            ledger.load("bad")

    def test_unsafe_session_id_rejected(self, tmp_path: Path) -> None:
        ledger = ManifestLedger(session_dir=tmp_path)
        # Session ID that sanitizes to empty (no [A-Za-z0-9_-] chars).
        with pytest.raises(ValueError):
            ledger.record("../../", _signed())
        with pytest.raises(ValueError):
            ledger.record("!!!", _signed())


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------


class TestManifestLedgerQueries:
    def test_find_by_source_id(self, tmp_path: Path) -> None:
        ledger = ManifestLedger(session_dir=tmp_path)
        ledger.record("s", _signed(source_id="alpha"))
        ledger.record("s", _signed(source_id="beta"))
        ledger.record("s", _signed(source_id="alpha"))
        results = ledger.find_by_source_id("alpha", session_id="s")
        assert len(results) == 2
        assert all("alpha" in e.manifest.declared_source_ids() for e in results)

    def test_find_by_kind(self, tmp_path: Path) -> None:
        ledger = ManifestLedger(session_dir=tmp_path)
        m_web = ContextManifest(system_id="t")
        m_web.add(ContextSource(kind=SourceKind.WEB_SEARCH, source_id="w"))
        m_web.sign(SECRET)
        ledger.record("s", _signed())
        ledger.record("s", m_web)
        web = ledger.find_by_kind(SourceKind.WEB_SEARCH, session_id="s")
        vdb = ledger.find_by_kind(SourceKind.VECTOR_DB, session_id="s")
        assert len(web) == 1
        assert len(vdb) == 1

    def test_clear_cache(self, tmp_path: Path) -> None:
        ledger = ManifestLedger(session_dir=tmp_path)
        ledger.record("s", _signed())
        ledger.clear_cache("s")
        # Still loadable from disk.
        assert len(ledger.load("s")) == 1

    def test_clear_cache_all(self, tmp_path: Path) -> None:
        ledger = ManifestLedger(session_dir=tmp_path)
        ledger.record("a", _signed())
        ledger.record("b", _signed())
        ledger.clear_cache()
        assert len(ledger.load("a")) == 1
        assert len(ledger.load("b")) == 1

    def test_scan_sessions_enumerates_disk(self, tmp_path: Path) -> None:
        first = ManifestLedger(session_dir=tmp_path)
        first.record("alpha", _signed())
        first.record("beta", _signed())
        # Fresh instance, cold cache — must still discover from disk.
        second = ManifestLedger(session_dir=tmp_path)
        assert second.scan_sessions() == ["alpha", "beta"]

    def test_scan_sessions_missing_dir(self, tmp_path: Path) -> None:
        ledger = ManifestLedger(session_dir=tmp_path / "nope")
        assert ledger.scan_sessions() == []

    def test_load_all_rehydrates_every_session(self, tmp_path: Path) -> None:
        first = ManifestLedger(session_dir=tmp_path)
        first.record("s1", _signed())
        first.record("s2", _signed())
        second = ManifestLedger(session_dir=tmp_path)
        loaded = second.load_all()
        assert set(loaded.keys()) == {"s1", "s2"}
        assert all(len(v) == 1 for v in loaded.values())


# ---------------------------------------------------------------------------
# verify_signatures
# ---------------------------------------------------------------------------


class TestLedgerVerifySignatures:
    def test_all_valid(self, tmp_path: Path) -> None:
        ledger = ManifestLedger(session_dir=tmp_path)
        ledger.record("s", _signed())
        ledger.record("s", _signed())
        bad = ledger.verify_signatures("s", SECRET)
        assert bad == []

    def test_wrong_key_all_bad(self, tmp_path: Path) -> None:
        ledger = ManifestLedger(session_dir=tmp_path)
        ledger.record("s", _signed())
        bad = ledger.verify_signatures("s", SECRET2)
        assert len(bad) == 1

    def test_unsigned_flagged(self, tmp_path: Path) -> None:
        ledger = ManifestLedger(session_dir=tmp_path)
        m = ContextManifest(system_id="t")
        m.add(ContextSource(kind=SourceKind.VECTOR_DB, source_id="v"))
        # No sign()
        ledger.record("s", m)
        bad = ledger.verify_signatures("s", SECRET)
        assert len(bad) == 1


# ---------------------------------------------------------------------------
# EnvVarKeyProvider
# ---------------------------------------------------------------------------


class TestEnvVarKeyProvider:
    def test_reads_utf8(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CRP_TEST_SECRET", "x" * 32)
        kp = EnvVarKeyProvider("CRP_TEST_SECRET")
        assert kp.current() == b"x" * 32

    def test_reads_hex(self, monkeypatch: pytest.MonkeyPatch) -> None:
        hex_str = "ab" * 32  # 64 hex chars -> 32 bytes
        monkeypatch.setenv("CRP_TEST_SECRET", hex_str)
        kp = EnvVarKeyProvider("CRP_TEST_SECRET")
        assert kp.current() == bytes.fromhex(hex_str)

    def test_short_secret_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CRP_TEST_SECRET", "short")
        kp = EnvVarKeyProvider("CRP_TEST_SECRET")
        with pytest.raises(ManifestValidationError):
            kp.current()

    def test_allow_short_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CRP_TEST_SECRET", "short")
        kp = EnvVarKeyProvider("CRP_TEST_SECRET", allow_short=True)
        assert kp.current() == b"short"

    def test_missing_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("CRP_TEST_SECRET", raising=False)
        kp = EnvVarKeyProvider("CRP_TEST_SECRET")
        with pytest.raises(ManifestValidationError):
            kp.current()

    def test_verify_uses_current(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CRP_TEST_SECRET", "x" * 32)
        kp = EnvVarKeyProvider("CRP_TEST_SECRET")
        m = _signed(secret=b"x" * 32)
        assert kp.verify(m) is True
        m_bad = _signed(secret=b"y" * 32)
        assert kp.verify(m_bad) is False


# ---------------------------------------------------------------------------
# RotatingKeyProvider
# ---------------------------------------------------------------------------


class TestRotatingKeyProvider:
    def test_initial_signs_and_verifies(self) -> None:
        kp = RotatingKeyProvider(initial=SECRET)
        m = _signed(secret=SECRET)
        assert kp.verify(m) is True

    def test_rotate_keeps_old_valid(self) -> None:
        kp = RotatingKeyProvider(initial=SECRET)
        m_old = _signed(secret=SECRET)
        kp.rotate(SECRET2)
        # Current is new
        assert kp.current() == SECRET2
        # Old manifest still verifies via retired key
        assert kp.verify(m_old) is True
        # New manifests sign with current
        m_new = _signed(secret=kp.current())
        assert kp.verify(m_new) is True

    def test_retire_all_drops_old(self) -> None:
        kp = RotatingKeyProvider(initial=SECRET)
        m_old = _signed(secret=SECRET)
        kp.rotate(SECRET2)
        kp.retire_all()
        assert kp.verify(m_old) is False

    def test_max_retired_caps_ring(self) -> None:
        kp = RotatingKeyProvider(initial=b"k0" * 16, max_retired=2)
        kp.rotate(b"k1" * 16)
        kp.rotate(b"k2" * 16)
        kp.rotate(b"k3" * 16)
        cands = list(kp.candidates())
        # current + 2 retired = 3
        assert len(cands) == 3
        assert cands[0] == b"k3" * 16

    def test_empty_key_rejected(self) -> None:
        with pytest.raises(ManifestValidationError):
            RotatingKeyProvider(initial=b"")
        kp = RotatingKeyProvider(initial=SECRET)
        with pytest.raises(ManifestValidationError):
            kp.rotate(b"")

    def test_candidates_order(self) -> None:
        kp = RotatingKeyProvider(initial=SECRET)
        kp.rotate(SECRET2)
        cands = list(kp.candidates())
        assert cands[0] == SECRET2  # current first
        assert cands[1] == SECRET   # retired second
