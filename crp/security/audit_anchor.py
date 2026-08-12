# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""External anchoring for the compliance audit trail (§7.14, SPEC-011).

Anchoring commits a trail to a single Merkle root (see
``crp.security.audit_merkle``) and publishes that commitment to an external
medium, so later tampering with the local trail is detectable by anyone
holding the anchor. The flow mirrors RFC 3161 timestamping:

  1. compute the Merkle root over all trail ``entry_hash`` values,
  2. build an :class:`AnchorRecord` (root, entry count, ISO-8601 timestamp,
     method) — the "timestamp token",
  3. sign the canonical record bytes with an Ed25519 :class:`ActionSigner`
     when one is available (unsigned in zero-dependency mode),
  4. persist via a pluggable :class:`AnchorTransport`.

``LocalFileTransport`` is the v1 anchor transport; a TSA HTTP transport
(e.g. an RFC 3161 Time-Stamp Authority client) can slot in by implementing
the same two-method interface without touching the anchor/verify logic.
"""

from __future__ import annotations

import hashlib
import hmac as _hmac
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from crp.security.audit_merkle import MerkleTree
from crp.security.audit_trail import ActionSigner, ComplianceAuditTrail

logger = logging.getLogger("crp.security.audit_anchor")

ANCHOR_VERSION = "1.0"


@dataclass
class AnchorRecord:
    """A signed, timestamped commitment to a trail's Merkle root.

    Attributes:
        root_hash: Merkle root over the trail's entry hashes (hex).
        entry_count: Number of trail entries covered by the root.
        anchored_at: ISO-8601 UTC timestamp of anchoring.
        method: Anchor transport method tag (e.g. ``"local-file"``).
        version: Anchor record schema version.
        signature: Hex Ed25519 signature over :meth:`tbs_bytes` ("" when unsigned).
        signer_public_key: PEM public key for signature verification ("" when unsigned).
    """

    root_hash: str
    entry_count: int
    anchored_at: str
    method: str = "local-file"
    version: str = ANCHOR_VERSION
    signature: str = ""
    signer_public_key: str = ""

    def tbs_bytes(self) -> bytes:
        """Canonical to-be-signed bytes (RFC-3161-style: fixed field set,
        sorted keys, compact separators — signature fields excluded)."""
        return json.dumps(
            {
                "anchored_at": self.anchored_at,
                "entry_count": self.entry_count,
                "method": self.method,
                "root_hash": self.root_hash,
                "version": self.version,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")

    def to_dict(self) -> dict[str, Any]:
        """Serialise the record to a JSON-safe dict."""
        return {
            "version": self.version,
            "method": self.method,
            "root_hash": self.root_hash,
            "entry_count": self.entry_count,
            "anchored_at": self.anchored_at,
            "signature": self.signature,
            "signer_public_key": self.signer_public_key,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AnchorRecord:
        """Deserialise a record; raises ``ValueError`` on missing fields."""
        try:
            return cls(
                root_hash=str(data["root_hash"]),
                entry_count=int(data["entry_count"]),
                anchored_at=str(data["anchored_at"]),
                method=str(data.get("method", "local-file")),
                version=str(data.get("version", ANCHOR_VERSION)),
                signature=str(data.get("signature", "")),
                signer_public_key=str(data.get("signer_public_key", "")),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"malformed anchor record: {exc}") from exc


# ---------------------------------------------------------------------------
# Pluggable anchor transports
# ---------------------------------------------------------------------------


class AnchorTransport(ABC):
    """Transport that persists and retrieves anchor records.

    Implementations: :class:`LocalFileTransport` (v1). A TSA HTTP client
    (RFC 3161) or transparency-log submitter slots in here later.
    """

    @abstractmethod
    def write(self, record: AnchorRecord) -> None:
        """Persist ``record`` to the external medium."""

    @abstractmethod
    def read(self) -> AnchorRecord:
        """Retrieve the previously persisted record."""


@dataclass
class LocalFileTransport(AnchorTransport):
    """v1 anchor transport: a JSON file on local (or mounted) storage."""

    path: str | Path

    def write(self, record: AnchorRecord) -> None:
        """Write the record as pretty-printed JSON (atomic-ish via direct write)."""
        Path(self.path).write_text(
            json.dumps(record.to_dict(), indent=2) + "\n", encoding="utf-8"
        )

    def read(self) -> AnchorRecord:
        """Read and parse the record file; raises ``ValueError`` if malformed."""
        try:
            data = json.loads(Path(self.path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"cannot read anchor file {self.path}: {exc}") from exc
        return AnchorRecord.from_dict(data)


def _snake_tag(name: str) -> str:
    """CamelCase → kebab-ish lower tag (``LocalFile`` → ``local-file``)."""
    out: list[str] = []
    for ch in name:
        if ch.isupper() and out:
            out.append("-")
        out.append(ch.lower())
    return "".join(out)


def _method_tag(transport: AnchorTransport) -> str:
    """Derive a stable method tag from the transport class name."""
    name = type(transport).__name__
    tag = name[: -len("Transport")] if name.endswith("Transport") else name
    return _snake_tag(tag)


# ---------------------------------------------------------------------------
# Anchor / verify
# ---------------------------------------------------------------------------


def _trail_root(trail: ComplianceAuditTrail) -> tuple[str, int]:
    """Compute the Merkle root over all trail entry hashes."""
    entries = trail.query()
    tree = MerkleTree([e.entry_hash for e in entries])
    return tree.root(), len(entries)


def anchor_trail(
    trail: ComplianceAuditTrail,
    transport: AnchorTransport,
    signer: ActionSigner | None = None,
) -> AnchorRecord:
    """Anchor ``trail`` via ``transport``; returns the persisted record.

    Args:
        trail: The compliance audit trail to commit to.
        transport: Where the anchor record goes.
        signer: Ed25519 signer for the record. When omitted, one is created
            (``CRP_AUDIT_SIGNING_KEY`` env or ephemeral) if ``cryptography``
            is installed; in zero-dependency mode the record is unsigned.
    """
    root, count = _trail_root(trail)
    record = AnchorRecord(
        root_hash=root,
        entry_count=count,
        anchored_at=datetime.now(timezone.utc).isoformat(),
        method=getattr(transport, "method", None) or _method_tag(transport),
    )
    if signer is None:
        try:
            signer = ActionSigner()
        except ImportError:
            signer = None  # zero-dependency mode: unsigned anchor
    if signer is not None:
        digest = hashlib.sha256(record.tbs_bytes()).hexdigest()
        record.signature = signer.sign(digest)
        record.signer_public_key = signer.public_key_pem().decode("ascii")
    transport.write(record)
    logger.info(
        "Anchored trail: root=%s entries=%d method=%s signed=%s",
        root[:16] or "(empty)", count, record.method, bool(record.signature),
    )
    return record


def anchor_to_file(
    trail: ComplianceAuditTrail,
    path: str | Path,
    signer: ActionSigner | None = None,
) -> AnchorRecord:
    """Convenience wrapper: anchor ``trail`` to a local JSON file at ``path``."""
    return anchor_trail(trail, LocalFileTransport(path), signer=signer)


def verify_anchor(
    trail: ComplianceAuditTrail,
    anchor_path: str | Path,
    transport: AnchorTransport | None = None,
) -> bool:
    """Verify ``trail`` against a previously written anchor.

    Recomputes the Merkle root over the current trail and compares it (and
    the entry count) to the anchored record. When the record is signed, the
    Ed25519 signature must also verify — a signed record whose signature
    cannot be checked (malformed, wrong key, or ``cryptography`` unavailable)
    fails closed.

    Returns False on any mismatch, tampering, or unreadable anchor.
    """
    transport = transport or LocalFileTransport(anchor_path)
    try:
        record = transport.read()
    except ValueError:
        logger.error("Anchor unreadable or malformed: %s", anchor_path)
        return False

    root, count = _trail_root(trail)
    if record.entry_count != count or not _hmac.compare_digest(record.root_hash, root):
        logger.error(
            "Anchor mismatch: record(root=%s, n=%d) vs trail(root=%s, n=%d)",
            record.root_hash[:16], record.entry_count, root[:16], count,
        )
        return False

    if record.signature:
        try:
            digest = hashlib.sha256(record.tbs_bytes()).hexdigest()
            if not ActionSigner.verify(
                record.signer_public_key.encode("ascii"), digest, record.signature
            ):
                logger.error("Anchor signature invalid")
                return False
        except ImportError:
            logger.error("Signed anchor but 'cryptography' is unavailable; failing closed")
            return False
    return True
