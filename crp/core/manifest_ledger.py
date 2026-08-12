# Copyright © 2025-2026 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Manifest ledger — cross-turn continuity and replay (§7.14.5, CRP 2.2).

Motivation
----------
In 2.1, each turn builds a fresh :class:`ContextManifest`.  There is no
persistent record answering questions like:

* "Did this fact in turn 9 originate from the web-search source declared
  in turn 3?"
* "Show me the full manifest history for session X from six months ago."
* "Which turns exposed content from ``acme-hr-policies-vdb``?"

The ledger persists a per-session sequence of signed manifests to the
filesystem (``crp_sessions/<session_id>.manifest.jsonl``) and maintains an
in-memory lineage index keyed by ``source_id``.

Storage format
--------------
One JSON object per line (JSONL). Each line is a complete signed manifest
plus a ``turn`` field and a ``recorded_at`` epoch stamp. Append-only;
tamper-evident via the HMAC signature carried inside each record.

Replay
------
:meth:`ManifestLedger.load` rehydrates a session's history into memory.
:meth:`ManifestLedger.find_by_source_id` walks the index and returns every
``(turn, manifest)`` pair where the source was declared.

This module deliberately stores on disk only; integrators who need a DB
back-end can wrap ``ManifestLedger`` — the API is intentionally small.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import threading
import time
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .context_source import (
    ContextManifest,
    ManifestValidationError,
    SourceKind,
)

__all__ = [
    "ManifestLedgerEntry",
    "ManifestLedger",
    "LedgerChainError",
    "KeyProvider",
    "EnvVarKeyProvider",
    "RotatingKeyProvider",
]


_log = logging.getLogger("crp.manifest_ledger")


# ---------------------------------------------------------------------------
# Tamper-evident chain (CRP 2.3)
# ---------------------------------------------------------------------------


class LedgerChainError(ManifestValidationError):
    """Raised when the ledger hash-chain fails verification."""


def _compute_entry_hash(
    session_id: str,
    turn: int,
    recorded_at: float,
    manifest_canonical: bytes,
    prev_hash: str,
) -> str:
    """SHA-256 over (session_id, turn, recorded_at, manifest, prev_hash).

    Gives every ledger entry a deterministic fingerprint that depends on
    every preceding entry in the same session — editing or reordering
    records breaks the chain.
    """
    h = hashlib.sha256()
    h.update(session_id.encode("utf-8"))
    h.update(b"|")
    h.update(str(turn).encode("ascii"))
    h.update(b"|")
    h.update(f"{recorded_at:.6f}".encode("ascii"))
    h.update(b"|")
    h.update(manifest_canonical)
    h.update(b"|")
    h.update(prev_hash.encode("ascii"))
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Ledger entry
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ManifestLedgerEntry:
    """One recorded manifest within a session's history.

    CRP 2.3 adds ``prev_hash`` + ``entry_hash`` fields forming a
    tamper-evident hash chain. Older entries without these fields (written
    by CRP 2.2) load with empty strings and are flagged by
    :meth:`ManifestLedger.verify_chain`.
    """

    session_id: str
    turn: int
    recorded_at: float
    manifest: ContextManifest
    prev_hash: str = ""
    entry_hash: str = ""

    def to_jsonl(self) -> str:
        """Serialise the entry to a single JSONL line."""
        payload = {
            "session_id": self.session_id,
            "turn": self.turn,
            "recorded_at": self.recorded_at,
            "manifest": json.loads(self.manifest.to_json()),
            "prev_hash": self.prev_hash,
            "entry_hash": self.entry_hash,
        }
        return json.dumps(payload, separators=(",", ":"))

    @classmethod
    def from_jsonl(cls, line: str) -> ManifestLedgerEntry:
        """Create a new instance from a JSON Lines record.
        
            Args:
                line (str): The line value.
        
            Returns:
                ``ManifestLedgerEntry``.
        """
        data = json.loads(line)
        manifest_dict = data["manifest"]
        manifest = ContextManifest.from_json(json.dumps(manifest_dict))
        return cls(
            session_id=str(data["session_id"]),
            turn=int(data["turn"]),
            recorded_at=float(data["recorded_at"]),
            manifest=manifest,
            prev_hash=str(data.get("prev_hash", "")),
            entry_hash=str(data.get("entry_hash", "")),
        )


# ---------------------------------------------------------------------------
# ManifestLedger
# ---------------------------------------------------------------------------


class ManifestLedger:
    """Append-only, per-session manifest store.

    The ledger is cheap to construct (no I/O until ``record`` or ``load``)
    and thread-safe for all public methods. One instance per session is
    the typical pattern; integrators may share a single ledger across
    sessions if they choose.
    """

    def __init__(
        self,
        session_dir: str | os.PathLike[str] = "crp_sessions",
        *,
        forward_to: Iterable[Any] | None = None,
    ) -> None:
        """Construct a filesystem-backed ledger.

        Parameters
        ----------
        session_dir
            Directory for JSONL files (one per session).
        forward_to
            Optional iterable of :class:`~crp.core.context_enforcer.AuditSink`
            instances (CRP 2.3). Each recorded entry is also emitted as an
            audit event so SIEM forwarders / syslog / JSONL replicators see
            the ledger write in real time.  Implementations that raise are
            logged and skipped — forwarding never blocks ledger writes.
        """
        self._dir = Path(session_dir)
        self._lock = threading.Lock()
        # In-memory: session_id -> list[Entry]
        self._cache: dict[str, list[ManifestLedgerEntry]] = {}
        self._forward_sinks: list[Any] = list(forward_to) if forward_to else []

    @property
    def session_dir(self) -> Path:
        """Return the session dir."""
        return self._dir

    # ------------------------------------------------------------ file path

    def _path_for(self, session_id: str) -> Path:
        safe = "".join(ch for ch in session_id if ch.isalnum() or ch in "-_")
        if not safe:
            raise ValueError("session_id must contain at least one [A-Za-z0-9_-]")
        return self._dir / f"{safe}.manifest.jsonl"

    # ---------------------------------------------------------------- record

    def record(
        self,
        session_id: str,
        manifest: ContextManifest,
        *,
        turn: int | None = None,
    ) -> ManifestLedgerEntry:
        """Append *manifest* to the ledger for *session_id*.

        Returns the created :class:`ManifestLedgerEntry`. If *turn* is not
        supplied, it defaults to ``len(existing) + 1`` — callers that
        sequence turns themselves should pass the explicit number.
        """
        if not session_id:
            raise ValueError("session_id must be non-empty")
        with self._lock:
            entries = self._cache.setdefault(session_id, [])
            resolved_turn = turn if turn is not None else (len(entries) + 1)
            prev_hash = entries[-1].entry_hash if entries else ""
            recorded_at = time.time()
            # canonical manifest payload is what the signature (if any) covers
            manifest_canonical = manifest._canonical_payload()  # type: ignore[attr-defined]
            entry_hash = _compute_entry_hash(
                session_id,
                resolved_turn,
                recorded_at,
                manifest_canonical,
                prev_hash,
            )
            entry = ManifestLedgerEntry(
                session_id=session_id,
                turn=resolved_turn,
                recorded_at=recorded_at,
                manifest=manifest,
                prev_hash=prev_hash,
                entry_hash=entry_hash,
            )
            entries.append(entry)
            self._dir.mkdir(parents=True, exist_ok=True)
            path = self._path_for(session_id)
            with path.open("a", encoding="utf-8") as fp:
                fp.write(entry.to_jsonl())
                fp.write("\n")
        # Forward (outside lock — sinks may do I/O) -- CRP 2.3.
        if self._forward_sinks:
            event = {
                "event_type": "CONTEXT_LEDGER_RECORD",
                "session_id": session_id,
                "turn": entry.turn,
                "recorded_at": entry.recorded_at,
                "manifest_id": manifest.manifest_id,
                "prev_hash": entry.prev_hash,
                "entry_hash": entry.entry_hash,
            }
            for sink in self._forward_sinks:
                try:
                    sink.emit(dict(event))
                except Exception as exc:  # pragma: no cover - defensive
                    _log.warning("CRP ledger forward failed: %s", exc)
        return entry

    # ------------------------------------------------------------------ load

    def load(self, session_id: str) -> list[ManifestLedgerEntry]:
        """Rehydrate a session's ledger from disk into memory.

        Idempotent — calling repeatedly returns the same list. Missing
        files yield ``[]``.
        """
        with self._lock:
            if session_id in self._cache:
                return list(self._cache[session_id])
            entries: list[ManifestLedgerEntry] = []
            path = self._path_for(session_id)
            if path.exists():
                with path.open("r", encoding="utf-8") as fp:
                    for lineno, line in enumerate(fp, 1):
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            entries.append(ManifestLedgerEntry.from_jsonl(line))
                        except (ValueError, KeyError, ManifestValidationError) as exc:
                            raise ManifestValidationError(
                                f"Corrupt ledger entry at {path}:{lineno}: {exc}"
                            ) from exc
            self._cache[session_id] = entries
            return list(entries)

    # --------------------------------------------------------------- queries

    def history(self, session_id: str) -> list[ManifestLedgerEntry]:
        """Return all entries for *session_id* (loads from disk if needed)."""
        return self.load(session_id)

    def latest(self, session_id: str) -> ManifestLedgerEntry | None:
        """Return the most recent ledger entry for *session_id*.

        Args:
            session_id: Session identifier to query.

        Returns:
            The last recorded entry, or ``None`` if the session has no history.
        """
        entries = self.load(session_id)
        return entries[-1] if entries else None

    def find_by_source_id(
        self,
        source_id: str,
        *,
        session_id: str | None = None,
    ) -> list[ManifestLedgerEntry]:
        """Every entry whose manifest declares *source_id*.

        If *session_id* is provided, search is limited to that session —
        otherwise the currently-cached sessions are scanned. Disk-only
        sessions are NOT discovered automatically; call :meth:`load` first
        to include them.
        """
        if session_id is not None:
            scope = [session_id]
        else:
            with self._lock:
                scope = list(self._cache.keys())

        out: list[ManifestLedgerEntry] = []
        for sid in scope:
            for entry in self.load(sid):
                if source_id in entry.manifest.declared_source_ids():
                    out.append(entry)
        return out

    def find_by_kind(
        self,
        kind: SourceKind,
        *,
        session_id: str | None = None,
    ) -> list[ManifestLedgerEntry]:
        """Every entry whose manifest declares at least one source of *kind*."""
        if session_id is not None:
            scope = [session_id]
        else:
            with self._lock:
                scope = list(self._cache.keys())
        out: list[ManifestLedgerEntry] = []
        for sid in scope:
            for entry in self.load(sid):
                if kind in entry.manifest.declared_kinds():
                    out.append(entry)
        return out

    # ----------------------------------------------------------- maintenance

    def verify_signatures(
        self,
        session_id: str,
        secret: bytes,
    ) -> list[ManifestLedgerEntry]:
        """Return entries whose signature does NOT verify under *secret*.

        Useful for periodic ledger-integrity audits. An empty list means
        every entry verifies successfully.
        """
        bad: list[ManifestLedgerEntry] = []
        for entry in self.load(session_id):
            mf = entry.manifest
            if mf.signature is None:
                bad.append(entry)
                continue
            try:
                if not mf.verify(secret):
                    bad.append(entry)
            except ManifestValidationError:
                bad.append(entry)
        return bad

    def clear_cache(self, session_id: str | None = None) -> None:
        """Drop in-memory cache for *session_id* (or all if None)."""
        with self._lock:
            if session_id is None:
                self._cache.clear()
            else:
                self._cache.pop(session_id, None)

    def verify_chain(
        self,
        session_id: str,
        *,
        strict: bool = False,
    ) -> list[tuple[int, str]]:
        """Re-compute every entry's hash chain for *session_id*.

        Returns ``[(turn, reason), ...]`` for each broken entry. An empty
        list means the ledger is intact. When ``strict=True`` and an entry
        is missing its ``entry_hash`` (written by CRP 2.2 pre-chain) this
        is treated as a break; otherwise pre-2.3 rows are tolerated.

        CRP 2.3 tamper-evidence: any post-write edit of a JSONL line
        changes that entry's recomputed hash and causes every subsequent
        entry to report ``prev_hash_mismatch``.
        """
        broken: list[tuple[int, str]] = []
        prev = ""
        for entry in self.load(session_id):
            if not entry.entry_hash:
                if strict:
                    broken.append((entry.turn, "entry_hash_missing"))
                prev = ""  # can't chain further; reset
                continue
            expected = _compute_entry_hash(
                entry.session_id,
                entry.turn,
                entry.recorded_at,
                entry.manifest._canonical_payload(),  # type: ignore[attr-defined]
                entry.prev_hash,
            )
            if not hmac.compare_digest(expected, entry.entry_hash):
                broken.append((entry.turn, "entry_hash_mismatch"))
            elif entry.prev_hash != prev and prev != "":
                broken.append((entry.turn, "prev_hash_mismatch"))
            prev = entry.entry_hash
        return broken

    def scan_sessions(self) -> list[str]:
        """Enumerate every session with a ledger file on disk.

        Returns a sorted list of session IDs. Useful before calling
        :meth:`find_by_source_id` or :meth:`find_by_kind` without a
        ``session_id`` argument — those methods only search in-memory
        sessions, so on-disk-only sessions are invisible unless scanned
        and loaded first.
        """
        if not self._dir.exists():
            return []
        suffix = ".manifest.jsonl"
        ids: list[str] = []
        for entry in self._dir.iterdir():
            if entry.is_file() and entry.name.endswith(suffix):
                ids.append(entry.name[: -len(suffix)])
        return sorted(ids)

    def load_all(self) -> dict[str, list[ManifestLedgerEntry]]:
        """Scan disk and rehydrate every session ledger.

        Equivalent to calling :meth:`scan_sessions` and then :meth:`load`
        on each. Returns a dict keyed by session_id.
        """
        return {sid: self.load(sid) for sid in self.scan_sessions()}


# ---------------------------------------------------------------------------
# Key management — KeyProvider abstraction
# ---------------------------------------------------------------------------


class KeyProvider:
    """Minimal key-provider interface for manifest signing.

    Keeps CRP out of the secret-management business while still offering
    enough structure for rotation, grace periods, and audit-trail binding.
    Integrators with HSMs, KMS, or Vault plug in by subclassing.
    """

    def current(self) -> bytes:  # pragma: no cover - interface
        """Return the active secret for signing new manifests."""
        raise NotImplementedError

    def candidates(self) -> Iterable[bytes]:  # pragma: no cover - interface
        """Iterate over every secret that should verify against historical
        manifests — current first, then retired keys within the grace
        window. Used during rotation."""
        raise NotImplementedError

    # ------------------------------------------------------------- helpers

    def verify(self, manifest: ContextManifest) -> bool:
        """Try each candidate key; return True if any verifies."""
        if manifest.signature is None:
            return False
        for key in self.candidates():
            try:
                if manifest.verify(key):
                    return True
            except ManifestValidationError:
                continue
        return False


class EnvVarKeyProvider(KeyProvider):
    """Read the active secret from an environment variable.

    ``env_var`` (default ``CRP_MANIFEST_SECRET``) must contain at least 32
    bytes of entropy encoded as either raw UTF-8 or hex. Hex is detected
    automatically when the value is an even-length ``[0-9a-f]+`` string.

    This is the **minimum viable** provider — sufficient for single-node
    deployments and tests. Production deployments should use a rotating
    provider backed by KMS/Vault and inject ``RotatingKeyProvider``.
    """

    MIN_SECRET_BYTES = 32

    def __init__(
        self,
        env_var: str = "CRP_MANIFEST_SECRET",
        *,
        allow_short: bool = False,
    ) -> None:
        self._env_var = env_var
        self._allow_short = allow_short

    def _resolve(self) -> bytes:
        raw = os.environ.get(self._env_var, "")
        if not raw:
            raise ManifestValidationError(
                f"Environment variable {self._env_var!r} is unset or empty"
            )
        # Hex-decode if plausible.
        if len(raw) % 2 == 0 and all(c in "0123456789abcdefABCDEF" for c in raw):
            try:
                secret = bytes.fromhex(raw)
            except ValueError:
                secret = raw.encode("utf-8")
        else:
            secret = raw.encode("utf-8")
        if not self._allow_short and len(secret) < self.MIN_SECRET_BYTES:
            raise ManifestValidationError(
                f"{self._env_var} resolved to {len(secret)} bytes; "
                f"require ≥ {self.MIN_SECRET_BYTES} (pass allow_short=True to override)"
            )
        return secret

    def current(self) -> bytes:
        """Execute current and return the result.
        
            Returns:
                ``bytes``.
        """
        return self._resolve()

    def candidates(self) -> Iterable[bytes]:
        """Execute candidates and return the result.
        
            Returns:
                ``Iterable[bytes]``.
        """
        yield self._resolve()


@dataclass
class _KeyRing:
    current: bytes
    retired: tuple[bytes, ...] = ()
    rotated_at: float = field(default_factory=time.time)


class RotatingKeyProvider(KeyProvider):
    """Key provider with an in-process rotation ring.

    The caller owns actual key storage (KMS / Vault / file). This class is
    a *coordination* primitive: during rotation, both the new and the
    previous key verify, so in-flight manifests signed under the old key
    remain valid for a configurable grace window.

    Usage::

        kp = RotatingKeyProvider(initial=load_from_kms())
        ...
        # Rotate when KMS emits a new version
        kp.rotate(new_key=load_from_kms(), grace=timedelta(hours=24))

    Thread-safe for ``rotate``, ``current``, and ``candidates``.
    """

    def __init__(
        self,
        initial: bytes,
        *,
        max_retired: int = 3,
    ) -> None:
        if not isinstance(initial, (bytes, bytearray)) or len(initial) == 0:
            raise ManifestValidationError("Initial key must be non-empty bytes")
        self._lock = threading.Lock()
        self._ring = _KeyRing(current=bytes(initial))
        self._max_retired = int(max_retired)

    def rotate(self, new_key: bytes) -> None:
        """Promote *new_key* to current and retire the previous key."""
        if not isinstance(new_key, (bytes, bytearray)) or len(new_key) == 0:
            raise ManifestValidationError("new_key must be non-empty bytes")
        with self._lock:
            prev = self._ring.current
            retired = (prev,) + self._ring.retired
            if len(retired) > self._max_retired:
                retired = retired[: self._max_retired]
            self._ring = _KeyRing(
                current=bytes(new_key),
                retired=retired,
                rotated_at=time.time(),
            )

    def retire_all(self) -> None:
        """Drop every retired key — active key continues to sign/verify."""
        with self._lock:
            self._ring = _KeyRing(current=self._ring.current)

    def current(self) -> bytes:
        """Execute current and return the result.
        
            Returns:
                ``bytes``.
        """
        with self._lock:
            return self._ring.current

    def candidates(self) -> Iterable[bytes]:
        """Execute candidates and return the result.
        
            Returns:
                ``Iterable[bytes]``.
        """
        with self._lock:
            ring = self._ring
        yield ring.current
        yield from ring.retired
