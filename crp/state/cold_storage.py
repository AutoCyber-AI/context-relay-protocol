# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Cold storage — Tier 3 cross-session persistence (§3.6).

Persists facts, graph structure, community IDs, and metadata to disk.
PersistedStateHeader provides schema versioning + integrity checksums.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .event_log import FactEventLog
from .warm_store import WarmStateStore

# ---------------------------------------------------------------------------
# Persisted state header
# ---------------------------------------------------------------------------

COLD_SCHEMA_VERSION = 1


@dataclass
class PersistedStateHeader:
    """Schema-versioned header for cold storage files (§3.6)."""

    schema_version: int = COLD_SCHEMA_VERSION
    created_at: float = field(default_factory=time.time)
    session_id: str = ""
    fact_count: int = 0
    edge_count: int = 0
    window_count: int = 0
    checksum: str = ""  # BLAKE3 or SHA-256 of payload
    hmac_signature: str = ""  # HMAC chain signature (§4G.3)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the persisted-state header to a dict."""
        return {
            "schema_version": self.schema_version,
            "created_at": self.created_at,
            "session_id": self.session_id,
            "fact_count": self.fact_count,
            "edge_count": self.edge_count,
            "window_count": self.window_count,
            "checksum": self.checksum,
            "hmac_signature": self.hmac_signature,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PersistedStateHeader:
        """Create a new instance from a dictionary.
        
            Args:
                data (dict[str, Any]): The data value.
        
            Returns:
                ``PersistedStateHeader``.
        """
        return cls(
            schema_version=data.get("schema_version", COLD_SCHEMA_VERSION),
            created_at=data.get("created_at", 0.0),
            session_id=data.get("session_id", ""),
            fact_count=data.get("fact_count", 0),
            edge_count=data.get("edge_count", 0),
            window_count=data.get("window_count", 0),
            checksum=data.get("checksum", ""),
            hmac_signature=data.get("hmac_signature", ""),
        )


# ---------------------------------------------------------------------------
# Cold storage operations
# ---------------------------------------------------------------------------


def _compute_checksum(payload: str) -> str:
    """Compute integrity checksum (BLAKE3 preferred, SHA-256 fallback)."""
    try:
        import blake3  # type: ignore[import-untyped]

        return blake3.blake3(payload.encode()).hexdigest()
    except ImportError:
        return hashlib.sha256(payload.encode()).hexdigest()


def persist_to_cold(
    warm_store: WarmStateStore,
    event_log: FactEventLog,
    path: str | Path,
    session_id: str = "",
    community_map: dict[str, int] | None = None,
    hmac_key: bytes | None = None,
) -> PersistedStateHeader:
    """Persist warm store + event log to cold storage.

    File format: JSON with header + payload.
    Includes community IDs (§4E.1) and HMAC chain (§4G.3) when provided.
    Uses atomic writes to prevent partial-write corruption (§4G.4).
    """
    store_data = warm_store.to_dict()
    event_data = event_log.to_list()

    payload: dict[str, Any] = {
        "warm_store": store_data,
        "event_log": event_data,
    }

    # Include community IDs if available (§4E.1)
    if community_map:
        payload["community_map"] = community_map

    payload_str = json.dumps(payload, sort_keys=True, default=str)

    header = PersistedStateHeader(
        session_id=session_id,
        fact_count=warm_store.fact_count,
        edge_count=len(warm_store.graph.edges),
        window_count=warm_store.window_count,
        checksum=_compute_checksum(payload_str),
    )

    # Compute HMAC chain signature if key provided (§4G.3)
    if hmac_key:
        import hmac as _hmac
        header.hmac_signature = _hmac.new(
            hmac_key, payload_str.encode(), hashlib.sha256
        ).hexdigest()

    cold_data = {
        "header": header.to_dict(),
        "payload": payload,
    }

    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)

    # Atomic write: write to temp, then rename (§4G.4)
    tmp = p.with_suffix(".tmp")
    try:
        tmp.write_text(json.dumps(cold_data, default=str), encoding="utf-8")
        # os.replace is atomic on POSIX; best-effort on Windows
        os.replace(str(tmp), str(p))
    except BaseException:
        # Clean up partial temp file on failure
        tmp.unlink(missing_ok=True)
        raise

    return header


def restore_from_cold(
    warm_store: WarmStateStore,
    event_log: FactEventLog,
    path: str | Path,
    hmac_key: bytes | None = None,
) -> tuple[PersistedStateHeader, list[str], dict[str, int]]:
    """Load cold storage into warm store + event log.

    Returns (header, warnings, community_map) where:
    - warnings list integrity issues
    - community_map has restored community assignments (§4E.1)

    Performs HMAC chain verification when key provided (§4G.3).
    Handles partial-write corruption (§4G.4).
    Applies schema migrations (§4G.2).
    """
    p = Path(path)
    warnings: list[str] = []
    community_map: dict[str, int] = {}

    if not p.exists():
        # Check for temp file from interrupted atomic write (§4G.4)
        tmp = p.with_suffix(".tmp")
        if tmp.exists():
            warnings.append("Found interrupted write (.tmp file); attempting recovery")
            try:
                cold_data = json.loads(tmp.read_text(encoding="utf-8"))
                warnings.append("Recovered from .tmp file")
            except (json.JSONDecodeError, OSError):
                warnings.append(f"Cold storage file not found and .tmp is corrupt: {path}")
                return PersistedStateHeader(), warnings, community_map
        else:
            warnings.append(f"Cold storage file not found: {path}")
            return PersistedStateHeader(), warnings, community_map
    else:
        try:
            cold_data = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            warnings.append(f"Failed to read cold storage: {exc}")
            return PersistedStateHeader(), warnings, community_map

    header = PersistedStateHeader.from_dict(cold_data.get("header", {}))
    payload = cold_data.get("payload", {})

    # Schema migration (§4G.2)
    if header.schema_version < COLD_SCHEMA_VERSION:
        warnings.append(
            f"Migrating schema v{header.schema_version} → v{COLD_SCHEMA_VERSION}"
        )
        payload = _migrate_payload(payload, header.schema_version, COLD_SCHEMA_VERSION)
    elif header.schema_version > COLD_SCHEMA_VERSION:
        warnings.append(
            f"Schema version {header.schema_version} is newer than current "
            f"{COLD_SCHEMA_VERSION} — forward compat may lose data"
        )

    # Verify checksum
    payload_str = json.dumps(payload, sort_keys=True, default=str)
    expected_checksum = _compute_checksum(payload_str)
    integrity_failed = False
    if header.checksum and header.checksum != expected_checksum:
        warnings.append("Checksum verification FAILED — data may be corrupted")
        integrity_failed = True

    # Verify HMAC chain (§4G.3)
    if hmac_key and header.hmac_signature:
        import hmac as _hmac
        expected_hmac = _hmac.new(
            hmac_key, payload_str.encode(), hashlib.sha256
        ).hexdigest()
        if not _hmac.compare_digest(header.hmac_signature, expected_hmac):
            warnings.append("HMAC chain verification FAILED — data may be tampered")
            integrity_failed = True
    elif hmac_key and not header.hmac_signature:
        warnings.append("HMAC key provided but no HMAC signature in stored data")

    # SECURITY: fail-closed — reject corrupted/tampered data (§audit5 SEC-H1)
    if integrity_failed:
        warnings.append("REJECTED: data not loaded due to integrity failure")
        return header, warnings, community_map

    # Load warm store
    warm_store.load_from_dict(payload.get("warm_store", {}))

    # Load event log
    event_log.load_from_list(payload.get("event_log", []))

    # Restore community IDs (§4E.1)
    if "community_map" in payload:
        community_map = payload["community_map"]

    # Verify counts
    if header.fact_count != warm_store.fact_count:
        warnings.append(
            f"Fact count mismatch: header={header.fact_count}, "
            f"loaded={warm_store.fact_count}"
        )

    return header, warnings, community_map


def _migrate_payload(
    payload: dict[str, Any],
    from_version: int,
    to_version: int,
) -> dict[str, Any]:
    """Apply schema migrations sequentially (§4G.2)."""
    # Currently only v1 exists. Future migrations will be added here:
    # if from_version < 2:
    #     payload = _migrate_v1_to_v2(payload)
    return payload
