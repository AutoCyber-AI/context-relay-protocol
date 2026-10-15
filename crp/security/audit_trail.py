# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Tamper-evident compliance audit trail — HMAC-signed, immutable (§7.14).

Upgrades the observability audit log (§8.9) with:
  - HMAC-SHA256 chained signatures (tamper-evident)
  - Compliance-specific event types (data access, consent, erasure)
  - Structured export for regulatory review
  - Retention management for audit records
  - ISO 42001 / EU AI Act Article 12 compliant record-keeping

EU AI Act: Art. 12 (record-keeping), Art. 13 (transparency)
ISO 42001: A.6.2.8 (records management), 9.1 (performance monitoring)
"""

from __future__ import annotations

import hashlib
import hmac as _hmac
import json
import logging
import os
import threading
import time
import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Any

logger = logging.getLogger("crp.security.audit_trail")


def atomic_write_text(path: str, text: str) -> None:
    """Atomically and durably write ``text`` to ``path`` (audit U-C9).

    tmp-file + fsync + ``os.replace`` + directory fsync: a crash mid-write
    can never leave a truncated file at the destination (the previous
    pre-6.2.2 close-time ``open(path, "w")`` export could, and the result
    looked authoritative).
    """
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as fh:
        fh.write(text)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp_path, path)
    try:
        dir_fd = os.open(os.path.dirname(path) or ".", os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    except OSError:  # pragma: no cover - best effort on exotic filesystems
        pass


class _DurableAuditWriter:
    """Crash-durable JSONL appender for audit trail entries (audit U-C9).

    Appends one line per recorded entry so a process crash mid-session
    leaves previously recorded events on disk — before this existed the
    whole in-memory trail was lost unless ``close()`` ran cleanly, and the
    close-time export itself was a non-atomic ``open(path, "w")``.

    Lines are flushed every append and fsync'd every ``fsync_every``
    appends (and on :meth:`flush`).  The clean close path later rewrites
    the same file atomically from the authoritative in-memory chain, so
    the append log is a crash-safety net, not the final format.
    """

    def __init__(self, path: str, fsync_every: int = 1) -> None:
        self._path = path
        self._fsync_every = max(1, int(fsync_every))
        self._fh = open(path, "a", encoding="utf-8")
        self._appends = 0

    @property
    def path(self) -> str:
        return self._path

    def append(self, entry_dict: dict) -> None:
        """Append one entry line; flush always, fsync per policy."""
        self._fh.write(json.dumps(entry_dict, separators=(",", ":")) + "\n")
        self._fh.flush()
        self._appends += 1
        if self._appends % self._fsync_every == 0:
            os.fsync(self._fh.fileno())

    def flush(self) -> None:
        """Flush + fsync any buffered line (called at clean close)."""
        self._fh.flush()
        os.fsync(self._fh.fileno())

    def close(self) -> None:
        try:
            self.flush()
        finally:
            self._fh.close()


# ---------------------------------------------------------------------------
# Ed25519 action receipts (audit_v2) — optional, zero-dependency safe
# ---------------------------------------------------------------------------


def _require_ed25519():
    """Import the Ed25519 primitives lazily; friendly error when absent.

    ``cryptography`` is an optional dependency (``pip install crprotocol[security]``).
    The audit trail works exactly as before when it is not installed — receipts
    are simply not produced.
    """
    try:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.ed25519 import (
            Ed25519PrivateKey,
            Ed25519PublicKey,
        )
    except ImportError:
        raise ImportError(
            "Ed25519 audit receipts require the 'cryptography' package. "
            "Install with: pip install crprotocol[security]"
        ) from None
    return Ed25519PrivateKey, Ed25519PublicKey, serialization


class ActionSigner:
    """Ed25519 signer for per-entry audit receipts (audit_v2).

    Each audit entry's ``entry_hash`` is signed, producing a non-repudiable
    receipt verifiable against the signer's public key alone — unlike the
    symmetric HMAC chain, a verifier needs no shared secret.

    Key resolution order:
      1. explicit ``private_key_path`` argument, then
      2. ``CRP_AUDIT_SIGNING_KEY`` env var (path to a PEM private key), then
      3. an ephemeral keypair generated for the process lifetime.

    Args:
        private_key_path: Path to a PEM-encoded Ed25519 private key.

    Raises:
        ImportError: If ``cryptography`` is not installed.
    """

    def __init__(self, private_key_path: str | None = None) -> None:
        Ed25519PrivateKey, _, serialization = _require_ed25519()
        self._serialization = serialization
        path = private_key_path or os.environ.get("CRP_AUDIT_SIGNING_KEY")
        if path:
            with open(path, "rb") as fh:
                self._private_key = serialization.load_pem_private_key(
                    fh.read(), password=None
                )
            logger.info("ActionSigner loaded Ed25519 key from %s", path)
        else:
            self._private_key = Ed25519PrivateKey.generate()
            logger.info("ActionSigner using ephemeral Ed25519 keypair")

    def public_key_pem(self) -> bytes:
        """PEM-encoded Ed25519 public key (safe to distribute to verifiers)."""
        serialization = self._serialization
        return self._private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )

    def sign(self, entry_hash: str) -> str:
        """Sign an audit entry hash; returns the Ed25519 signature as hex."""
        return self._private_key.sign(bytes.fromhex(entry_hash)).hex()

    @staticmethod
    def verify(public_key_pem: bytes, entry_hash: str, signature_hex: str) -> bool:
        """Verify a receipt against a PEM public key.

        Returns False (never raises) on any malformed input, wrong key, or
        invalid signature.

        Raises:
            ImportError: If ``cryptography`` is not installed.
        """
        _, Ed25519PublicKey, serialization = _require_ed25519()
        try:
            public_key = serialization.load_pem_public_key(public_key_pem)
            if not isinstance(public_key, Ed25519PublicKey):
                return False
            public_key.verify(bytes.fromhex(signature_hex), bytes.fromhex(entry_hash))
            return True
        except Exception:  # malformed input or cryptography.exceptions.InvalidSignature
            return False


# ---------------------------------------------------------------------------
# Compliance event types
# ---------------------------------------------------------------------------


class ComplianceEventType(str, Enum):
    """Compliance-grade event types beyond standard CRP events (§7.14.1)."""

    # Data lifecycle
    DATA_INGESTED = "compliance.data_ingested"
    DATA_PROCESSED = "compliance.data_processed"
    DATA_ACCESSED = "compliance.data_accessed"
    DATA_EXPORTED = "compliance.data_exported"
    DATA_DELETED = "compliance.data_deleted"
    DATA_CLASSIFIED = "compliance.data_classified"
    DATA_RECLASSIFIED = "compliance.data_reclassified"

    # Consent
    CONSENT_GRANTED = "compliance.consent_granted"
    CONSENT_DENIED = "compliance.consent_denied"
    CONSENT_WITHDRAWN = "compliance.consent_withdrawn"

    # Privacy
    PII_DETECTED = "compliance.pii_detected"
    ERASURE_REQUESTED = "compliance.erasure_requested"
    ERASURE_COMPLETED = "compliance.erasure_completed"
    RETENTION_EXPIRED = "compliance.retention_expired"
    RETENTION_PURGED = "compliance.retention_purged"

    # Security
    SECURITY_THREAT_DETECTED = "compliance.security_threat"
    INJECTION_DETECTED = "compliance.injection_detected"
    AUTH_FAILURE = "compliance.auth_failure"
    RATE_LIMIT_HIT = "compliance.rate_limit_hit"
    RBAC_DENIED = "compliance.rbac_denied"

    # Human oversight
    OVERSIGHT_APPROVAL_REQUESTED = "compliance.oversight_requested"
    OVERSIGHT_APPROVED = "compliance.oversight_approved"
    OVERSIGHT_DENIED = "compliance.oversight_denied"
    OVERSIGHT_HALT = "compliance.oversight_halt"

    # Session lifecycle
    SESSION_CREATED = "compliance.session_created"
    SESSION_CLOSED = "compliance.session_closed"

    # Risk
    RISK_ASSESSMENT = "compliance.risk_assessment"
    RISK_LEVEL_CHANGED = "compliance.risk_level_changed"

    # LLM decision provenance (§7.14.2)
    ENVELOPE_CONTEXT_SELECTED = "compliance.envelope_context_selected"
    LLM_CALL_COMPLETED = "compliance.llm_call_completed"
    FACTS_EXTRACTED = "compliance.facts_extracted"
    CONTINUATION_DECIDED = "compliance.continuation_decided"
    QUALITY_TIER_ASSIGNED = "compliance.quality_tier_assigned"

    # Decision Provenance Engine (§7.14.3)
    CLAIM_ATTRIBUTED = "compliance.claim_attributed"
    ATTRIBUTION_REPORT = "compliance.attribution_report"
    PARAMETRIC_DETECTED = "compliance.parametric_detected"
    ATTRIBUTION_UNCERTAIN = "compliance.attribution_uncertain"

    # Fidelity Verification Layer (§7.14.3)
    DISTORTION_DETECTED = "compliance.distortion_detected"
    OMISSION_DETECTED = "compliance.omission_detected"
    FABRICATION_DETECTED = "compliance.fabrication_detected"
    CONTRADICTION_DETECTED = "compliance.contradiction_detected"

    # Semantic Entailment Verification (§7.14.3)
    ENTAILMENT_CONTRADICTION = "compliance.entailment_contradiction"
    ENTAILMENT_VERIFIED = "compliance.entailment_verified"

    # Hallucination Risk Assessment (§7.14.3)
    HALLUCINATION_RISK_HIGH = "compliance.hallucination_risk_high"
    HALLUCINATION_RISK_CRITICAL = "compliance.hallucination_risk_critical"
    RISK_ASSESSMENT_COMPLETED = "compliance.risk_assessment_completed"

    # Provenance Engine Operational Events (§7.14.3)
    PROVENANCE_ENGINE_FAILURE = "compliance.provenance_engine_failure"
    PROVENANCE_DISABLED = "compliance.provenance_disabled"
    ENTAILMENT_MODEL_STATUS = "compliance.entailment_model_status"

    # Response Quality Assurance — RQA v3.0 (CRP-SPEC-005 §16-19)
    REPETITION_DETECTED = "compliance.repetition_detected"
    COMPLETENESS_CONTINUATION = "compliance.completeness_continuation"
    FLOW_DEGRADED = "compliance.flow_degraded"
    QUALITY_SCORE_ASSIGNED = "compliance.quality_score_assigned"
    RE_DISPATCH = "compliance.re_dispatch"

    # Progressive activation & adaptive mode (CRP-SPEC-017)
    MODE_TRANSITION = "compliance.mode_transition"
    ACTIVATION_STAGE_CHANGED = "compliance.activation_stage_changed"
    ONBOARDING_COMPLETED = "compliance.onboarding_completed"

    # Window provenance DAG (CRP-SPEC-004)
    WINDOW_HMAC_GENERATED = "compliance.window_hmac_generated"
    CHAIN_INTEGRITY_VERIFIED = "compliance.chain_integrity_verified"
    CHAIN_INTEGRITY_BROKEN = "compliance.chain_integrity_broken"
    FAN_IN_MERGED = "compliance.fan_in_merged"

    # Transcript capture (schema 2.1.0 — docs/FIX_NOTE_transcript_capture.md)
    # Emitted once per window (primary + each continuation) when
    # ``CRP_AUDIT_CAPTURE_TRANSCRIPTS`` / ``audit_capture_transcripts`` is on.
    # Payload: {window_id, raw_output_id, input_hash, output_hash,
    #           transcript_ref, bytes_in, bytes_out, redacted, pii_types}
    TRANSCRIPT_RECORDED = "compliance.transcript_recorded"

    # Self-healing incident lifecycle (SPEC-033 §3.4; WASA self-healing loop).
    # Typed payloads — see INCIDENT_PAYLOAD_SHAPES / validate_incident_payload.
    INCIDENT_CAPTURED = "compliance.incident_captured"
    INCIDENT_DIAGNOSED = "compliance.incident_diagnosed"
    INCIDENT_REMEDIATED = "compliance.incident_remediated"
    INCIDENT_VERIFIED = "compliance.incident_verified"

    # Ingest quarantine validation counters (§7.8)
    QUARANTINE_VALIDATED = "compliance.quarantine_validated"


# ---------------------------------------------------------------------------
# Incident lifecycle payload shapes (SPEC-033 §3.4)
# ---------------------------------------------------------------------------

#: Canonical payload shapes for the INCIDENT_* event types.  Maps each event
#: type to ``field -> description``; :func:`validate_incident_payload` enforces
#: the required fields so self-healing loops emit first-class, machine-checkable
#: incident records instead of free-form strings.
#:
#: INCIDENT_CAPTURED  — an anomaly was observed and isolated:
#:   incident_id, session_id (engagement), component (tool/subsystem),
#:   classification (e.g. "tool_failure" | "anomalous_output" | "trust_decay"),
#:   evidence_refs (list of content hashes / artifact refs)
#: INCIDENT_DIAGNOSED — root-cause hypothesis recorded:
#:   incident_id, session_id, component, hypothesis, evidence_refs
#: INCIDENT_REMEDIATED — a corrective action was applied:
#:   incident_id, session_id, action (enum), state_before, state_after
#: INCIDENT_VERIFIED  — post-remediation probe result:
#:   incident_id, session_id, probe_result
INCIDENT_PAYLOAD_SHAPES: dict[str, dict[str, str]] = {
    ComplianceEventType.INCIDENT_CAPTURED.value: {
        "incident_id": "Unique incident identifier (links the lifecycle).",
        "session_id": "Engagement / session the incident belongs to.",
        "component": "Tool or subsystem the incident attaches to.",
        "classification": "Coarse incident class (e.g. tool_failure, anomalous_output).",
        "evidence_refs": "List of evidence references (content hashes / artifact ids).",
    },
    ComplianceEventType.INCIDENT_DIAGNOSED.value: {
        "incident_id": "Unique incident identifier (links the lifecycle).",
        "session_id": "Engagement / session the incident belongs to.",
        "component": "Tool or subsystem the incident attaches to.",
        "hypothesis": "Root-cause hypothesis recorded by the diagnoser.",
        "evidence_refs": "List of evidence references supporting the hypothesis.",
    },
    ComplianceEventType.INCIDENT_REMEDIATED.value: {
        "incident_id": "Unique incident identifier (links the lifecycle).",
        "session_id": "Engagement / session the incident belongs to.",
        "action": "Remediation action taken (enum, e.g. restart_service, swap_model).",
        "state_before": "Serializable component state before remediation.",
        "state_after": "Serializable component state after remediation.",
    },
    ComplianceEventType.INCIDENT_VERIFIED.value: {
        "incident_id": "Unique incident identifier (links the lifecycle).",
        "session_id": "Engagement / session the incident belongs to.",
        "probe_result": "Serializable probe outcome (pass/fail + measurements).",
    },
}

#: Allowed values for INCIDENT_REMEDIATED ``action`` (open enum — new actions
#: must be lowercase snake_case; unknown values validate with a warning-level
#: note via ``extra_fields``, never a hard error).
INCIDENT_ACTIONS: frozenset[str] = frozenset({
    "retry",
    "restart_service",
    "swap_model",
    "reduce_context",
    "gate_tool",
    "rollback",
    "escalate",
    "skip_step",
})


def validate_incident_payload(
    event_type: ComplianceEventType | str,
    data: dict[str, Any],
) -> list[str]:
    """Validate an INCIDENT_* event payload against its canonical shape.

    Args:
        event_type: One of the four INCIDENT_* event types (enum or value str).
        data: Event payload to validate.

    Returns:
        A list of problems (empty when the payload conforms).  Problems are
        strings of the form ``"missing field: <name>"`` or
        ``"bad type: <name> (expected <t>, got <t>)"``.  Non-incident event
        types return an empty list (no shape constraint).
    """
    evt = event_type.value if isinstance(event_type, ComplianceEventType) else event_type
    shape = INCIDENT_PAYLOAD_SHAPES.get(evt)
    if shape is None:
        return []
    problems: list[str] = []
    for field_name in shape:
        if field_name not in data or data[field_name] is None:
            problems.append(f"missing field: {field_name}")
    if evt == ComplianceEventType.INCIDENT_CAPTURED.value:
        refs = data.get("evidence_refs")
        if refs is not None and not isinstance(refs, list):
            problems.append(
                f"bad type: evidence_refs (expected list, got {type(refs).__name__})"
            )
        comp = data.get("component")
        if comp is not None and not isinstance(comp, str):
            problems.append(
                f"bad type: component (expected str, got {type(comp).__name__})"
            )
    if evt == ComplianceEventType.INCIDENT_REMEDIATED.value:
        action = data.get("action")
        if action is not None and not isinstance(action, str):
            problems.append(
                f"bad type: action (expected str, got {type(action).__name__})"
            )
    return problems


# ---------------------------------------------------------------------------
# Tamper-evident audit entry
# ---------------------------------------------------------------------------


@dataclass
class AuditEntry:
    """Single tamper-evident audit log entry (§7.14.2).

    Each entry includes an HMAC-SHA256 signature chained from the
    previous entry, creating a tamper-evident log. Modification of
    any entry invalidates all subsequent signatures.
    """

    entry_id: str
    event_type: str  # ComplianceEventType value or custom string
    timestamp: float
    session_id: str
    data: dict[str, Any]
    schema_version: str = "1.0.0"  # AuditEntry schema version (A-4)
    # Tamper-evidence fields
    sequence: int = 0  # Monotonic counter
    previous_hash: str = ""  # Hash of previous entry (chain link)
    entry_hash: str = ""  # HMAC-SHA256 of this entry's content
    signature: str = ""  # HMAC-SHA256(signing_key, entry_hash || previous_hash)
    # audit_v2: Ed25519 receipt over entry_hash (non-repudiable). Empty when no
    # ActionSigner is configured — the trail then works exactly as v1.
    receipt: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialise the audit entry to a JSON-safe dict.

        Returns:
            Dict representation including tamper-evidence fields.
        """
        return {
            "entry_id": self.entry_id,
            "event_type": self.event_type,
            "timestamp": self.timestamp,
            "session_id": self.session_id,
            "data": self.data,
            "schema_version": self.schema_version,
            "sequence": self.sequence,
            "previous_hash": self.previous_hash,
            "entry_hash": self.entry_hash,
            "signature": self.signature,
            "receipt": self.receipt,
        }


# ---------------------------------------------------------------------------
# Compliance audit trail
# ---------------------------------------------------------------------------


class ComplianceAuditTrail:
    """Tamper-evident, HMAC-signed compliance audit trail (§7.14).

    Provides an immutable, append-only log with cryptographic chaining
    that detects any modification to historical entries.

    EU AI Act Art. 12: "High-risk AI systems shall technically allow for
    the automatic recording of events (logs) over the lifetime of the system."

    ISO 42001 A.6.2.8: Organizations must maintain records of AI system
    development, deployment, operation, monitoring, and decommissioning.

    Usage::

        trail = ComplianceAuditTrail(signing_key=session_key)
        trail.record(
            ComplianceEventType.DATA_INGESTED,
            session_id="abc-123",
            data={"source": "user-input", "size_bytes": 4096},
        )
        # Verify chain integrity
        valid, broken_at = trail.verify_chain()
        assert valid
        # Export for regulatory review
        export = trail.export()
    """

    def __init__(
        self,
        signing_key: bytes | None = None,
        session_id: str = "",
        action_signer: ActionSigner | None = None,
    ) -> None:
        """Initialise the compliance audit trail.

        Args:
            signing_key: 32-byte HMAC key. If omitted, a random key is generated.
            session_id: Default session ID for entries that omit one.
            action_signer: Optional :class:`ActionSigner`. When provided, every
                entry additionally carries an Ed25519 ``receipt`` over its
                ``entry_hash`` and is marked ``schema_version="2.0.0"`` (audit_v2).
                When omitted, the trail behaves exactly as v1 (zero-dependency).
        """
        # Generate unique per-instance key if none provided (§audit4 SEC-C1)
        self._signing_key = signing_key or os.urandom(32)
        self._session_id = session_id
        self._action_signer = action_signer
        self._entries: list[AuditEntry] = []
        self._sequence = 0
        self._lock = threading.Lock()
        # Optional transcript store (attached by the orchestrator when
        # audit_capture_transcripts is enabled) — powers verify_transcripts()
        # and include_transcripts exports.
        self._transcript_store: Any | None = None
        # Crash-durable per-event append sink (audit U-C9) — None unless the
        # orchestrator enabled it via enable_durable_append().
        self._durable_writer: _DurableAuditWriter | None = None

    def enable_durable_append(self, path: str, fsync_every: int = 1) -> None:
        """Enable crash-durable per-event JSONL appending (audit U-C9).

        Every subsequently recorded entry is appended (and, per policy,
        fsync'd) so a process crash cannot lose the trail recorded so far.
        Idempotent: enabling twice keeps the first writer.
        """
        with self._lock:
            if self._durable_writer is None:
                os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
                self._durable_writer = _DurableAuditWriter(path, fsync_every)

    def flush_durable(self) -> None:
        """Flush + fsync the durable writer (clean close path)."""
        with self._lock:
            if self._durable_writer is not None:
                self._durable_writer.flush()

    def close_durable(self) -> None:
        """Flush, close and detach the durable writer (clean close path).

        Must run BEFORE any code rewrites ``durable_path`` atomically:
        on Windows an open append handle on the target makes
        ``os.replace`` fail with ``WinError 5`` (access denied), and any
        record() after this point would write to a closed file.  After
        close, :meth:`record` skips durable appending (in-memory chain is
        authoritative for the final export).
        """
        with self._lock:
            writer = self._durable_writer
            self._durable_writer = None
            if writer is not None:
                writer.close()

    @property
    def durable_path(self) -> str | None:
        """Path of the durable append log, when enabled."""
        w = self._durable_writer
        return w.path if w is not None else None

    def attach_transcript_store(self, store: Any) -> None:
        """Attach a :class:`crp.security.transcript_store.TranscriptStore`.

        Enables :meth:`verify_transcripts` and transcript-aware exports on
        this trail.  Called by the dispatch router the first time a transcript
        is captured for a session.
        """
        self._transcript_store = store

    @property
    def transcript_store(self) -> Any | None:
        """The attached transcript store, or None when capture is disabled."""
        return self._transcript_store

    @property
    def entry_count(self) -> int:
        """Number of entries currently stored in the trail."""
        return len(self._entries)

    def record(
        self,
        event_type: ComplianceEventType | str,
        session_id: str = "",
        data: dict[str, Any] | None = None,
    ) -> AuditEntry:
        """Append a tamper-evident entry to the audit trail.

        Thread-safe. Each entry is chained to the previous via HMAC.

        Args:
            event_type: Compliance event type enum or custom string.
            session_id: Session identifier. Falls back to the trail default.
            data: Arbitrary event payload.

        Returns:
            The newly created ``AuditEntry``.
        """
        with self._lock:
            now = time.time()
            sid = session_id or self._session_id
            evt = event_type.value if isinstance(event_type, ComplianceEventType) else event_type

            # Compute previous hash (chain link)
            previous_hash = self._entries[-1].entry_hash if self._entries else "0" * 64

            # Compute entry content hash
            content = json.dumps(
                {
                    "event_type": evt,
                    "timestamp": now,
                    "session_id": sid,
                    "data": data or {},
                    "sequence": self._sequence,
                },
                sort_keys=True,
                separators=(",", ":"),
            )
            entry_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

            # Compute HMAC signature (tamper-evidence)
            sig_input = f"{entry_hash}:{previous_hash}".encode()
            signature = _hmac.new(
                self._signing_key, sig_input, hashlib.sha256
            ).hexdigest()

            entry = AuditEntry(
                entry_id=f"audit-{uuid.uuid4().hex[:12]}",
                event_type=evt,
                timestamp=now,
                session_id=sid,
                data=data or {},
                sequence=self._sequence,
                previous_hash=previous_hash,
                entry_hash=entry_hash,
                signature=signature,
            )
            # audit_v2: non-repudiable Ed25519 receipt over the entry hash
            if self._action_signer is not None:
                entry.schema_version = "2.0.0"
                entry.receipt = self._action_signer.sign(entry_hash)
            # Transcript events carry the transcript-capable schema (2.1.0);
            # receipts still apply when a signer is configured.
            if evt == ComplianceEventType.TRANSCRIPT_RECORDED.value:
                entry.schema_version = "2.1.0"
            self._entries.append(entry)
            self._sequence += 1
            # Crash-durable append (audit U-C9) — never let the sink break
            # the audit record itself.
            writer = self._durable_writer
            if writer is not None:
                try:
                    writer.append(entry.to_dict())
                except OSError as exc:  # pragma: no cover - disk full etc.
                    logger.error("Durable audit append failed: %s", exc)

        return entry

    def verify_chain(
        self,
        verify_receipts: bool = False,
        public_key_pem: bytes | None = None,
    ) -> tuple[bool, int]:
        """Verify the integrity of the entire audit trail.

        Args:
            verify_receipts: Additionally verify each entry's Ed25519
                ``receipt`` (audit_v2). Every entry must carry a valid receipt;
                entries without one fail verification.
            public_key_pem: PEM public key for receipt verification. Falls back
                to the trail's configured :class:`ActionSigner` public key.

        Returns:
            ``(is_valid, broken_at_sequence)``. ``broken_at_sequence`` is ``-1``
            when the chain is valid, otherwise the sequence of the first broken entry.

        Raises:
            ValueError: If ``verify_receipts`` is True but no public key is
                available (neither argument nor configured signer).
        """
        with self._lock:
            receipt_key = public_key_pem
            if verify_receipts and receipt_key is None:
                if self._action_signer is None:
                    raise ValueError(
                        "verify_receipts=True requires public_key_pem or a "
                        "trail configured with an ActionSigner"
                    )
                receipt_key = self._action_signer.public_key_pem()

            if not self._entries:
                return True, -1

            for i, entry in enumerate(self._entries):
                # Verify chain link (genesis entry links to "0"*64)
                expected_prev = "0" * 64 if i == 0 else self._entries[i - 1].entry_hash

                if entry.previous_hash != expected_prev:
                    logger.error(
                        "Audit trail chain broken at sequence %d: "
                        "previous_hash mismatch",
                        entry.sequence,
                    )
                    return False, entry.sequence

                # Verify HMAC signature
                sig_input = f"{entry.entry_hash}:{entry.previous_hash}".encode()
                expected_sig = _hmac.new(
                    self._signing_key, sig_input, hashlib.sha256
                ).hexdigest()

                if not _hmac.compare_digest(entry.signature, expected_sig):
                    logger.error(
                        "Audit trail signature invalid at sequence %d",
                        entry.sequence,
                    )
                    return False, entry.sequence

                # audit_v2: verify Ed25519 receipt
                if verify_receipts and (
                    not entry.receipt
                    or not ActionSigner.verify(
                        receipt_key or b"", entry.entry_hash, entry.receipt
                    )
                ):
                    logger.error(
                        "Audit trail receipt invalid at sequence %d",
                        entry.sequence,
                    )
                    return False, entry.sequence

            return True, -1

    @classmethod
    def verify_file(
        cls,
        path: str,
        public_key_pem: bytes | None = None,
    ) -> tuple[bool, int]:
        """Offline verification of an exported audit JSONL file (A-PR-5 / I-C5).

        Recomputes each line's content hash from the exported fields — so ANY
        edit to the file is detected, unlike the keyless recompute-the-chain
        check integrators used to perform (the chain is plain SHA-256 over
        public fields and fully re-derivable by an editor) — validates the
        ``previous_hash`` linkage, and, when ``public_key_pem`` is supplied,
        requires a valid Ed25519 receipt on every entry.

        Args:
            path: Path to an exported ``<sid>.audit.jsonl`` file.
            public_key_pem: Optional Ed25519 public key (PEM) for strict
                audit_v2 receipt verification of every entry.

        Returns:
            ``(is_valid, broken_at_line)`` — 0-based JSONL line index of the
            first problem, or -1 when the file is valid.
        """
        try:
            with open(path, encoding="utf-8") as fh:
                lines = [ln for ln in fh.read().splitlines() if ln.strip()]
        except OSError as exc:
            logger.error("Cannot read audit file %s: %s", path, exc)
            return False, 0

        prev_hash = "0" * 64
        for i, line in enumerate(lines):
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                logger.error("Audit file line %d is not valid JSON", i)
                return False, i
            try:
                content = json.dumps(
                    {
                        "event_type": entry["event_type"],
                        "timestamp": entry["timestamp"],
                        "session_id": entry["session_id"],
                        "data": entry.get("data", {}),
                        "sequence": entry["sequence"],
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                )
            except (KeyError, TypeError):
                logger.error("Audit file line %d is missing required fields", i)
                return False, i
            entry_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
            if entry_hash != entry.get("entry_hash"):
                logger.error("Audit file content hash mismatch at line %d", i)
                return False, i
            if entry.get("previous_hash", "") != prev_hash:
                logger.error("Audit file chain link mismatch at line %d", i)
                return False, i
            if public_key_pem is not None and (
                not entry.get("receipt")
                or not ActionSigner.verify(public_key_pem, entry_hash, entry["receipt"])
            ):
                logger.error("Audit file receipt invalid at line %d", i)
                return False, i
            prev_hash = entry_hash
        return True, -1

    def verify_transcripts(self, *, session_id: str | None = None) -> Any:
        """Verify stored transcripts against this trail (schema 2.1.0).

        Companion to :meth:`verify_chain`: re-hashes stored transcript
        content and confirms it matches the ``TRANSCRIPT_RECORDED`` events
        and — for unredacted transcripts — the ``LLM_CALL_COMPLETED`` hashes
        already chained here.  An edited transcript flags at the exact window.

        Returns:
            :class:`crp.security.transcript_store.TranscriptVerification`.

        Raises:
            ValueError: If no transcript store is attached (capture disabled).
        """
        if self._transcript_store is None:
            raise ValueError(
                "No transcript store attached — enable audit_capture_transcripts "
                "(/ CRP_AUDIT_CAPTURE_TRANSCRIPTS) so transcripts are captured"
            )
        from crp.security.transcript_store import verify_transcripts

        return verify_transcripts(self._transcript_store, self, session_id=session_id)

    def _transcript_dicts(self) -> list[dict[str, Any]]:
        """Stored transcripts matching this trail's sessions, as dicts."""
        if self._transcript_store is None:
            return []
        try:
            records = [
                self._transcript_store.get(rid)
                for rid in self._transcript_store.list_ids()
            ]
        except Exception as exc:  # noqa: BLE001 — export must never raise
            logger.warning("Transcript listing failed during export: %s", exc)
            return []
        session_ids = {e.session_id for e in self._entries}
        out: list[dict[str, Any]] = []
        for rec in records:
            if rec is None:
                continue
            if session_ids and rec.session_id not in session_ids:
                continue
            out.append(rec.to_dict())
        return out

    def query(
        self,
        *,
        event_type: str | ComplianceEventType | None = None,
        session_id: str | None = None,
        since: float | None = None,
        until: float | None = None,
    ) -> list[AuditEntry]:
        """Query audit entries with optional filters.

        Args:
            event_type: Filter by event type.
            session_id: Filter by session ID.
            since: Include entries with timestamp >= this value.
            until: Include entries with timestamp <= this value.

        Returns:
            Matching ``AuditEntry`` objects in chronological order.
        """
        evt = (
            event_type.value
            if isinstance(event_type, ComplianceEventType)
            else event_type
        )

        with self._lock:
            results: list[AuditEntry] = []
            for entry in self._entries:
                if evt is not None and entry.event_type != evt:
                    continue
                if session_id is not None and entry.session_id != session_id:
                    continue
                if since is not None and entry.timestamp < since:
                    continue
                if until is not None and entry.timestamp > until:
                    continue
                results.append(entry)
            return results

    def export(
        self,
        *,
        include_signatures: bool = True,
        since: float | None = None,
    ) -> dict[str, Any]:
        """Export the full audit trail for regulatory review.

        Args:
            include_signatures: Whether to include HMAC signatures in the export.
            since: Only export entries with timestamp >= this value.

        Returns:
            Structured document suitable for compliance auditors, including
            chain integrity status and summary statistics.
        """
        valid, broken_at = self.verify_chain()

        with self._lock:
            entries = self._entries
            if since is not None:
                entries = [e for e in entries if e.timestamp >= since]

            # Summary statistics
            by_type: dict[str, int] = {}
            for e in entries:
                by_type[e.event_type] = by_type.get(e.event_type, 0) + 1

            export_data = {
                # Real schema version (audit U-C14b): entries carry per-entry
                # schema_version values ("1.0.0"/"2.0.0"/"2.1.0"); the export
                # envelope must expose the newest so consumers can detect
                # audit_v2 (2.0.0) / transcript-capable (2.1.0) chains.
                "audit_trail_version": max(
                    (getattr(e, "schema_version", "1.0.0") for e in entries),
                    default="1.0.0",
                ),
                "exported_at": time.time(),
                "chain_integrity": {
                    "valid": valid,
                    "broken_at_sequence": broken_at,
                    "total_entries": len(self._entries),
                },
                "summary": {
                    "entries_in_export": len(entries),
                    "by_event_type": by_type,
                    "earliest_timestamp": entries[0].timestamp if entries else None,
                    "latest_timestamp": entries[-1].timestamp if entries else None,
                },
                "entries": [
                    e.to_dict() if include_signatures else {
                        k: v
                        for k, v in e.to_dict().items()
                        if k not in ("signature", "entry_hash", "previous_hash", "receipt")
                    }
                    for e in entries
                ],
            }

        return export_data

    def export_jsonl(
        self,
        *,
        since: float | None = None,
        include_transcripts: bool = False,
    ) -> str:
        """Export as JSONL (one entry per line) for log aggregation.

        Args:
            since: Only export entries with timestamp >= this value.
            include_transcripts: When True (and a transcript store is
                attached), append the stored window transcripts as additional
                ``record_type="transcript"`` lines so the bundle is
                self-contained: chain + verdicts + viewable query–response
                pairs (schema 2.1.0).

        Returns:
            Newline-delimited JSON string of all matching entries.
        """
        with self._lock:
            entries = self._entries
            if since is not None:
                entries = [e for e in entries if e.timestamp >= since]
            lines = [json.dumps(e.to_dict(), separators=(",", ":")) for e in entries]
        if include_transcripts:
            lines.extend(
                json.dumps(t, separators=(",", ":")) for t in self._transcript_dicts()
            )
        return "\n".join(lines)

    # -- SIEM / regulatory export formats (CRP-SPEC-011 §4) -----------------

    def export_ndjson(self, *, since: float | None = None) -> str:
        """Alias for :meth:`export_jsonl` — NDJSON is the primary format (§4.1).

        Args:
            since: Only export entries with timestamp >= this value.

        Returns:
            Newline-delimited JSON string of all matching entries.
        """
        return self.export_jsonl(since=since)

    def export_ocsf(
        self,
        *,
        since: float | None = None,
        provider: str = "",
        model: str = "",
        include_transcripts: bool = False,
    ) -> list[dict[str, Any]]:
        """Export events in OCSF API Activity format for SIEMs (§4.2).

        Args:
            since: Only export entries with timestamp >= this value.
            provider: Provider identifier for the destination endpoint field.
            model: Model identifier for the destination endpoint field.
            include_transcripts: When True (and a transcript store is
                attached), TRANSCRIPT_RECORDED-derived records additionally
                carry the transcript reference and content hashes in
                ``unmapped`` (the transcript content itself stays in the
                attached store / :meth:`export_jsonl` bundle).

        Returns:
            List of OCSF ``class_uid=6003`` records. The HMAC and risk level
            are carried in the ``unmapped`` extension.
        """
        transcript_refs: dict[str, dict[str, Any]] = {}
        if include_transcripts:
            for t in self._transcript_dicts():
                rid = t.get("raw_output_id", "")
                if rid:
                    transcript_refs[rid] = {
                        "crp_transcript_ref": t.get("raw_output_id", ""),
                        "crp_transcript_output_sha256": t.get("output_sha256", ""),
                        "crp_transcript_bytes_out": t.get("bytes_out", 0),
                        "crp_transcript_redacted": t.get("redacted", False),
                    }
        with self._lock:
            entries = self._entries
            if since is not None:
                entries = [e for e in entries if e.timestamp >= since]
            dst = "+".join(p for p in (provider, model) if p)
            records: list[dict[str, Any]] = []
            for e in entries:
                unmapped: dict[str, Any] = {
                    "crp_hmac": e.signature,
                    "crp_entry_hash": e.entry_hash,
                    "crp_risk_level": e.data.get("risk_level", ""),
                    "crp_window_id": e.data.get("window_id", ""),
                    "crp_sequence": e.sequence,
                }
                rid = e.data.get("raw_output_id", "")
                if e.event_type == ComplianceEventType.TRANSCRIPT_RECORDED.value:
                    extra = transcript_refs.get(str(rid))
                    if extra:
                        unmapped.update(extra)
                records.append(
                    {
                        "class_uid": 6003,
                        "activity_id": _ocsf_activity_id(e.event_type),
                        "severity_id": _ocsf_severity_id(e.event_type, e.data),
                        "time": _iso8601(e.timestamp),
                        "src_endpoint": {"uid": e.session_id},
                        "dst_endpoint": {"uid": dst},
                        "metadata": {
                            "product": {
                                "name": "CRP Gateway",
                                "vendor_name": "AutoCyber AI",
                            },
                            "event_code": e.event_type,
                        },
                        "unmapped": unmapped,
                    }
                )
            return records

    def export_sarif(self, *, since: float | None = None) -> dict[str, Any]:
        """Export events as a SARIF 2.1.0 log for GitHub integration (§4.3).

        Args:
            since: Only export entries with timestamp >= this value.

        Returns:
            SARIF 2.1.0 log dict. Non-INFO events become SARIF results; INFO
            events are emitted at ``note`` level. Used by CRP Scan (CRP-SPEC-013).
        """
        with self._lock:
            entries = self._entries
            if since is not None:
                entries = [e for e in entries if e.timestamp >= since]
            results = [
                {
                    "ruleId": e.event_type,
                    "level": _sarif_level(e.event_type, e.data),
                    "message": {
                        "text": _sarif_message(e),
                    },
                    "properties": {
                        "session_id": e.session_id,
                        "window_id": e.data.get("window_id", ""),
                        "risk_level": e.data.get("risk_level", ""),
                        "timestamp": _iso8601(e.timestamp),
                        "hmac": e.signature,
                    },
                }
                for e in entries
            ]
        return {
            "version": "2.1.0",
            "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
            "runs": [
                {
                    "tool": {
                        "driver": {
                            "name": "CRP",
                            "informationUri": "https://crprotocol.io",
                            "version": "3.0.0",
                            "organization": "AutoCyber AI",
                        }
                    },
                    "results": results,
                }
            ],
        }


# ---------------------------------------------------------------------------
# Export mapping helpers (CRP-SPEC-011 §4)
# ---------------------------------------------------------------------------

# Events whose presence indicates a WARN-level (notable) condition.
_WARN_EVENTS = {
    ComplianceEventType.CHAIN_INTEGRITY_BROKEN.value,
    ComplianceEventType.FLOW_DEGRADED.value,
    ComplianceEventType.REPETITION_DETECTED.value,
}
# Events that map to error/critical severity.
_CRITICAL_EVENTS = {
    ComplianceEventType.CHAIN_INTEGRITY_BROKEN.value,
}


def _iso8601(ts: float) -> str:
    """Convert a Unix timestamp to an ISO 8601 UTC string."""
    from datetime import datetime, timezone

    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def _risk_is_high(data: dict[str, Any]) -> bool:
    """Return True if the event data indicates HIGH or CRITICAL risk."""
    return str(data.get("risk_level", "")).upper() in ("HIGH", "CRITICAL")


def _ocsf_activity_id(event_type: str) -> int:
    """Coarse OCSF activity id: 1=Create, 2=Read, 3=Update, 4=Delete, 99=Other."""
    if "created" in event_type or "completed" in event_type or "generated" in event_type:
        return 1
    if "retrieved" in event_type or "verified" in event_type:
        return 2
    if "transition" in event_type or "changed" in event_type or "merged" in event_type:
        return 3
    return 99


def _ocsf_severity_id(event_type: str, data: dict[str, Any]) -> int:
    """OCSF severity: 1=Informational, 3=Medium, 4=High, 5=Critical.

    Args:
        event_type: CRP compliance event type string.
        data: Event payload dict.

    Returns:
        OCSF severity integer.
    """

    if event_type in _CRITICAL_EVENTS or str(data.get("risk_level", "")).upper() == "CRITICAL":
        return 5
    if _risk_is_high(data):
        return 4
    if event_type in _WARN_EVENTS:
        return 3
    return 1


def _sarif_level(event_type: str, data: dict[str, Any]) -> str:
    """SARIF level: error | warning | note.

    Args:
        event_type: CRP compliance event type string.
        data: Event payload dict.

    Returns:
        SARIF level string.
    """

    if event_type in _CRITICAL_EVENTS or _risk_is_high(data):
        return "error"
    if event_type in _WARN_EVENTS:
        return "warning"
    return "note"


def _sarif_message(entry: AuditEntry) -> str:
    """Build a human-readable SARIF message from an audit entry.

    Args:
        entry: Audit entry to describe.

    Returns:
        Message text including event type, session id, and risk level if present.
    """
    risk = entry.data.get("risk_level", "")
    suffix = f" (risk={risk})" if risk else ""
    return f"{entry.event_type} in session {entry.session_id}{suffix}"
