# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Content-addressed transcript store for the compliance audit chain (§7.14).

The tamper-evident audit trail (:mod:`crp.security.audit_trail`) records
hashes and telemetry for LLM interactions — never the content.  Every window
mints ``WindowNode.raw_output_id`` but, before this module, nothing persisted
the raw output against that identifier.  ``TranscriptStore`` closes that gap:
it persists the assembled message array and raw output per window, keyed by
``raw_output_id`` and content hash, reusing the truncated SHA-256 hashes
already chained in ``LLM_CALL_COMPLETED`` so :func:`verify_transcripts` can
prove stored transcript content matches the chain — and flag tampering at the
exact window.

Capture is OFF by default (``CRP_AUDIT_CAPTURE_TRANSCRIPTS`` /
``audit_capture_transcripts``); when disabled the store is never touched and
no ``TRANSCRIPT_RECORDED`` events are emitted (zero overhead by default).

Design reference: ``docs/FIX_NOTE_transcript_capture.md`` (schema 2.1.0).
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from crp.security.audit_trail import AuditEntry, ComplianceAuditTrail
    from crp.security.privacy import PIIScanResult

logger = logging.getLogger("crp.security.transcript_store")

#: Schema version stamped on audit entries that carry transcript events (2.1.0).
TRANSCRIPT_SCHEMA_VERSION = "2.1.0"

#: Default per-transcript byte cap (1 MiB) — overridable via config/env.
DEFAULT_MAX_TRANSCRIPT_BYTES = 1_048_576

#: Env var for the on-disk transcript directory (config key ``audit_transcript_dir``
#: takes precedence when set).
ENV_TRANSCRIPT_DIR = "CRP_AUDIT_TRANSCRIPT_DIR"

_HASH_PREFIX_LEN = 16  # matches LLM_CALL_COMPLETED *_hash truncation


def hash_text(text: str) -> str:
    """Full SHA-256 hex digest of *text* (utf-8)."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def hash_messages(messages: list[dict[str, Any]]) -> str:
    """SHA-256 of the canonical JSON serialization of the message array."""
    blob = json.dumps(messages, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _prefix(digest: str) -> str:
    """Truncate a hex digest to the length used by LLM_CALL_COMPLETED."""
    return digest[:_HASH_PREFIX_LEN]


def redact_text(text: str, scan_result: PIIScanResult) -> str:
    """Replace PII detection spans with ``[REDACTED:<type>]`` markers.

    The scanner is advisory and never stores raw PII — only hashes and
    positions — so redaction is performed by span replacement over the
    caller's copy, never inside the scanner.

    Args:
        text: Original text (system prompt, task input, or output).
        scan_result: Result of :meth:`PIIScanner.scan` on *text*.

    Returns:
        Redacted text. When no PII was detected the input is returned
        unchanged.
    """
    if not scan_result.has_pii:
        return text
    # Replace from the end so earlier offsets stay valid.
    redacted = text
    for det in sorted(scan_result.detections, key=lambda d: d.position, reverse=True):
        marker = f"[REDACTED:{det.pii_type}]"
        redacted = redacted[: det.position] + marker + redacted[det.position + det.length :]
    return redacted


@dataclass
class TranscriptRecord:
    """One window's persisted transcript (messages + raw output).

    Content hashes are computed over the *stored* (possibly redacted)
    content so verification always compares like with like; the
    ``TRANSCRIPT_RECORDED`` audit event carries the same 16-char prefixes
    chained by ``LLM_CALL_COMPLETED``.
    """

    raw_output_id: str
    window_id: str
    session_id: str
    operation: str
    window_type: str = "primary"
    continuation_index: int = 0
    # Stored content (redacted variant when redaction is enabled).
    system_prompt: str = ""
    task_input: str = ""
    messages: list[dict[str, Any]] = field(default_factory=list)
    output: str = ""
    # Content hashes (full hex, sha256).  ``output_sha256`` always covers the
    # FULL pre-truncation output so the chain linkage survives the byte cap;
    # ``stored_output_sha256`` covers what is actually on disk (equal to
    # ``output_sha256`` unless ``truncated``).
    system_prompt_sha256: str = ""
    task_input_sha256: str = ""
    output_sha256: str = ""
    stored_output_sha256: str = ""
    messages_sha256: str = ""
    # Governance metadata.
    redacted: bool = False
    pii_types: list[str] = field(default_factory=list)
    bytes_in: int = 0
    bytes_out: int = 0
    stored_bytes: int = 0
    truncated: bool = False
    recorded_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-safe dict."""
        return {
            "record_type": "transcript",
            "schema_version": TRANSCRIPT_SCHEMA_VERSION,
            "raw_output_id": self.raw_output_id,
            "window_id": self.window_id,
            "session_id": self.session_id,
            "operation": self.operation,
            "window_type": self.window_type,
            "continuation_index": self.continuation_index,
            "system_prompt": self.system_prompt,
            "task_input": self.task_input,
            "messages": self.messages,
            "output": self.output,
            "system_prompt_sha256": self.system_prompt_sha256,
            "task_input_sha256": self.task_input_sha256,
            "output_sha256": self.output_sha256,
            "stored_output_sha256": self.stored_output_sha256,
            "messages_sha256": self.messages_sha256,
            "redacted": self.redacted,
            "pii_types": self.pii_types,
            "bytes_in": self.bytes_in,
            "bytes_out": self.bytes_out,
            "stored_bytes": self.stored_bytes,
            "truncated": self.truncated,
            "recorded_at": self.recorded_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TranscriptRecord:
        """Reconstruct a record from :meth:`to_dict` output."""
        known = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        kwargs = {k: v for k, v in data.items() if k in known}
        return cls(**kwargs)

    def recompute_hashes(self) -> dict[str, str]:
        """Re-hash the content as stored on disk; used by tamper verification."""
        return {
            "system_prompt_sha256": hash_text(self.system_prompt),
            "task_input_sha256": hash_text(self.task_input),
            "output_sha256": hash_text(self.output),
            "messages_sha256": hash_messages(self.messages),
        }

    def expected_output_hash(self) -> str:
        """Hash the stored output is expected to carry (stored variant when truncated)."""
        return self.stored_output_sha256 or self.output_sha256


class TranscriptStore:
    """Content-addressed store for per-window transcripts (§7.14).

    Records are persisted as one JSON file per ``raw_output_id`` under
    *storage_dir* plus a ``manifest.jsonl`` index.  When *storage_dir* is
    None the store is memory-only (useful for tests and ephemeral sessions).

    Size cap: serialized records larger than *max_bytes* have their raw
    ``output`` field head-truncated (``truncated=True``) so the cap is
    honoured on disk; content hashes of the FULL pre-truncation content are
    kept on the record and on the audit event, so the chain linkage survives
    truncation — the full output remains re-derivable from the caller.
    """

    def __init__(
        self,
        storage_dir: str | Path | None = None,
        *,
        max_bytes: int = DEFAULT_MAX_TRANSCRIPT_BYTES,
    ) -> None:
        self._dir: Path | None = Path(storage_dir) if storage_dir else None
        self._max_bytes = max(1024, int(max_bytes))
        self._memory: dict[str, TranscriptRecord] = {}
        self._lock = threading.Lock()
        if self._dir is not None:
            self._dir.mkdir(parents=True, exist_ok=True)

    @property
    def storage_dir(self) -> str | None:
        """On-disk directory, or None for memory-only storage."""
        return str(self._dir) if self._dir is not None else None

    @property
    def max_bytes(self) -> int:
        """Per-transcript serialized byte cap."""
        return self._max_bytes

    def _path_for(self, raw_output_id: str) -> Path | None:
        if self._dir is None:
            return None
        # Content-addressed: the id is a uuid minted per window; the file name
        # is the id itself so node.raw_output_id resolves directly.
        safe = "".join(c for c in raw_output_id if c.isalnum() or c in "-_")
        return self._dir / f"{safe}.json"

    def store(self, record: TranscriptRecord) -> str:
        """Persist *record*; returns the transcript reference (file path or id).

        Applies the byte cap: if the serialized record exceeds *max_bytes* the
        output field is head-truncated and ``truncated`` is set.  Full-content
        hashes are computed BEFORE truncation and stored on the record.
        """
        with self._lock:
            # Hash the full (pre-truncation) stored content.
            full = record.recompute_hashes()
            record.system_prompt_sha256 = full["system_prompt_sha256"]
            record.task_input_sha256 = full["task_input_sha256"]
            record.output_sha256 = full["output_sha256"]
            record.stored_output_sha256 = full["output_sha256"]
            record.messages_sha256 = full["messages_sha256"]
            record.bytes_in = sum(len(str(m)) for m in record.messages)
            record.bytes_out = len(record.output)

            blob = json.dumps(record.to_dict(), separators=(",", ":"), default=str)
            if len(blob.encode("utf-8")) > self._max_bytes and not record.truncated:
                budget = max(self._max_bytes // 2, 256)
                record.output = record.output[:budget] + "\n[... truncated by transcript byte cap ...]"
                record.truncated = True
                # The stored variant now hashes differently; keep the full
                # pre-truncation hash in output_sha256 for chain linkage.
                record.stored_output_sha256 = hash_text(record.output)
                blob = json.dumps(record.to_dict(), separators=(",", ":"), default=str)
            record.stored_bytes = len(blob.encode("utf-8"))

            path = self._path_for(record.raw_output_id)
            if path is not None:
                tmp = path.with_suffix(".tmp")
                tmp.write_text(blob, encoding="utf-8")
                os.replace(tmp, path)
                self._append_manifest(record, str(path))
                ref: str = str(path)
            else:
                self._memory[record.raw_output_id] = record
                ref = record.raw_output_id
        return ref

    def _append_manifest(self, record: TranscriptRecord, ref: str) -> None:
        if self._dir is None:
            return
        line = json.dumps(
            {
                "raw_output_id": record.raw_output_id,
                "window_id": record.window_id,
                "session_id": record.session_id,
                "ref": ref,
                "output_sha256": record.output_sha256,
                "recorded_at": record.recorded_at,
            },
            separators=(",", ":"),
        )
        with (self._dir / "manifest.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")

    def get(self, raw_output_id: str) -> TranscriptRecord | None:
        """Fetch a transcript by ``raw_output_id`` — resolves the dangling hook."""
        with self._lock:
            if raw_output_id in self._memory:
                return self._memory[raw_output_id]
            path = self._path_for(raw_output_id)
            if path is not None and path.is_file():
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError) as exc:
                    logger.warning("Transcript %s unreadable: %s", raw_output_id, exc)
                    return None
                return TranscriptRecord.from_dict(data)
        return None

    def list_ids(self) -> list[str]:
        """All stored transcript ids (memory + on-disk manifest)."""
        with self._lock:
            ids = set(self._memory)
            if self._dir is not None:
                manifest = self._dir / "manifest.jsonl"
                if manifest.is_file():
                    for line in manifest.read_text(encoding="utf-8").splitlines():
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            ids.add(json.loads(line)["raw_output_id"])
                        except (json.JSONDecodeError, KeyError):
                            continue
            return sorted(ids)

    def verify_entry(self, record: TranscriptRecord) -> list[str]:
        """Re-hash stored content and report fields that no longer match.

        Returns a list of human-readable mismatch descriptions (empty when
        the record is intact).  This detects post-hoc tampering with the
        stored transcript at this exact window.
        """
        mismatches: list[str] = []
        recomputed = record.recompute_hashes()
        for field_name, digest in recomputed.items():
            recorded = (
                record.expected_output_hash()
                if field_name == "output_sha256"
                else getattr(record, field_name)
            )
            if recorded and recorded != digest:
                mismatches.append(
                    f"{record.window_id}: {field_name} mismatch "
                    f"(recorded {recorded[:16]}…, recomputed {digest[:16]}…)"
                )
        return mismatches


@dataclass
class TranscriptVerification:
    """Outcome of :func:`verify_transcripts`."""

    valid: bool = True
    checked: int = 0
    mismatches: list[dict[str, Any]] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    unmatched_events: list[str] = field(default_factory=list)


def verify_transcripts(
    store: TranscriptStore,
    trail: ComplianceAuditTrail,
    *,
    session_id: str | None = None,
) -> TranscriptVerification:
    """Prove stored transcripts match the compliance audit chain (§7.14).

    For every ``TRANSCRIPT_RECORDED`` event in *trail* (optionally filtered by
    *session_id*):

    1. The stored record must exist (by ``raw_output_id``) — otherwise the
       event is listed in ``missing``.
    2. The record's stored content is re-hashed and compared against the
       hashes recorded on the TRANSCRIPT_RECORDED event itself (``input_hash`` /
       ``output_hash``) — an edited transcript file flags here, at the exact
       ``window_id``.
    3. When the event was NOT redacted, the stored ``system_prompt`` /
       ``task_input`` are additionally compared against the 16-char hashes in
       the window's ``LLM_CALL_COMPLETED`` entry, reusing the hashes already
       chained there.  Redacted transcripts skip this step by design (the
       stored content is intentionally different from what was hashed for
       the chain).

    ``valid`` is True only when nothing is missing and no mismatch occurred.
    """
    result = TranscriptVerification()
    events = trail.query(event_type="compliance.transcript_recorded", session_id=session_id)

    llm_calls: dict[str, AuditEntry] = {}
    for entry in trail.query(
        event_type="compliance.llm_call_completed", session_id=session_id
    ):
        wid = entry.data.get("window_id")
        if isinstance(wid, str):
            llm_calls[wid] = entry

    for event in events:
        data = event.data
        raw_output_id = str(data.get("raw_output_id", ""))
        window_id = str(data.get("window_id", ""))
        record = store.get(raw_output_id) if raw_output_id else None
        if record is None:
            result.missing.append(window_id or raw_output_id)
            result.valid = False
            continue

        result.checked += 1
        redacted = bool(data.get("redacted", False))

        # (2) stored content must match the hashes recorded on the event.
        local = store.verify_entry(record)
        if local:
            result.valid = False
            for desc in local:
                result.mismatches.append({"window_id": window_id, "detail": desc})
            continue

        event_input_hash = str(data.get("input_hash", ""))
        event_output_hash = str(data.get("output_hash", ""))
        if event_input_hash and event_input_hash != _prefix(record.task_input_sha256):
            result.valid = False
            result.mismatches.append(
                {
                    "window_id": window_id,
                    "detail": (
                        f"{window_id}: input_hash mismatch against "
                        f"TRANSCRIPT_RECORDED event "
                        f"(event {event_input_hash}, stored {_prefix(record.task_input_sha256)})"
                    ),
                }
            )
        if event_output_hash and event_output_hash != _prefix(record.output_sha256):
            result.valid = False
            result.mismatches.append(
                {
                    "window_id": window_id,
                    "detail": (
                        f"{window_id}: output_hash mismatch against "
                        f"TRANSCRIPT_RECORDED event "
                        f"(event {event_output_hash}, stored {_prefix(record.output_sha256)})"
                    ),
                }
            )

        # (3) unredacted transcripts must also match the chain's LLM_CALL_COMPLETED.
        if not redacted:
            call = llm_calls.get(window_id)
            if call is not None:
                call_input = str(call.data.get("task_input_hash", ""))
                if call_input and call_input != _prefix(record.task_input_sha256):
                    result.valid = False
                    result.mismatches.append(
                        {
                            "window_id": window_id,
                            "detail": (
                                f"{window_id}: task_input_hash mismatch against "
                                f"LLM_CALL_COMPLETED "
                                f"(chain {call_input}, stored {_prefix(record.task_input_sha256)})"
                            ),
                        }
                    )
                call_sys = str(call.data.get("system_prompt_hash", ""))
                if call_sys and call_sys != _prefix(record.system_prompt_sha256):
                    result.valid = False
                    result.mismatches.append(
                        {
                            "window_id": window_id,
                            "detail": (
                                f"{window_id}: system_prompt_hash mismatch against "
                                f"LLM_CALL_COMPLETED "
                                f"(chain {call_sys}, stored {_prefix(record.system_prompt_sha256)})"
                            ),
                        }
                    )

    stored_ids = set(store.list_ids())
    event_ids = {str(e.data.get("raw_output_id", "")) for e in events}
    result.unmatched_events = sorted(i for i in stored_ids if i and i not in event_ids)
    return result


def new_raw_output_id() -> str:
    """Mint a raw-output identifier (kept here so store and router agree)."""
    return str(uuid.uuid4())


__all__ = [
    "TRANSCRIPT_SCHEMA_VERSION",
    "DEFAULT_MAX_TRANSCRIPT_BYTES",
    "ENV_TRANSCRIPT_DIR",
    "TranscriptRecord",
    "TranscriptStore",
    "TranscriptVerification",
    "hash_text",
    "hash_messages",
    "redact_text",
    "verify_transcripts",
    "new_raw_output_id",
]
