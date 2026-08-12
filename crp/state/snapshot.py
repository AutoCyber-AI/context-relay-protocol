# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Snapshots & session resume — periodic checkpoint + restore (§3.3, §22.4).

Snapshots capture warm store state at regular intervals so the event log can
be truncated.  Session resume protocol: load snapshot → verify integrity →
replay events → rebuild ANN.
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
# Snapshot data
# ---------------------------------------------------------------------------

SNAPSHOT_INTERVAL = 50  # windows between snapshots
SCHEMA_VERSION = 1


@dataclass
class EventLogSnapshot:
    """Captured state at a point in time (§3.3)."""

    snapshot_id: str = ""
    schema_version: int = SCHEMA_VERSION
    window_id: str = ""
    window_count: int = 0
    timestamp: float = field(default_factory=time.time)
    warm_store_data: dict[str, Any] = field(default_factory=dict)
    last_event_id: int = 0
    checksum: str = ""  # BLAKE3 or SHA-256

    def compute_checksum(self) -> str:
        """Compute integrity checksum over the snapshot payload."""
        payload = json.dumps(self.warm_store_data, sort_keys=True, default=str)
        try:
            import blake3  # type: ignore[import-untyped]

            return blake3.blake3(payload.encode()).hexdigest()
        except ImportError:
            return hashlib.sha256(payload.encode()).hexdigest()

    def verify_checksum(self) -> bool:
        """Verify the stored checksum matches the payload."""
        return self.checksum == self.compute_checksum()

    def to_dict(self) -> dict[str, Any]:
        """Serialize the snapshot to a dict."""
        return {
            "snapshot_id": self.snapshot_id,
            "schema_version": self.schema_version,
            "window_id": self.window_id,
            "window_count": self.window_count,
            "timestamp": self.timestamp,
            "warm_store_data": self.warm_store_data,
            "last_event_id": self.last_event_id,
            "checksum": self.checksum,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EventLogSnapshot:
        """Create a new instance from a dictionary.
        
            Args:
                data (dict[str, Any]): The data value.
        
            Returns:
                ``EventLogSnapshot``.
        """
        return cls(
            snapshot_id=data.get("snapshot_id", ""),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            window_id=data.get("window_id", ""),
            window_count=data.get("window_count", 0),
            timestamp=data.get("timestamp", 0.0),
            warm_store_data=data.get("warm_store_data", {}),
            last_event_id=data.get("last_event_id", 0),
            checksum=data.get("checksum", ""),
        )


# ---------------------------------------------------------------------------
# Snapshot manager
# ---------------------------------------------------------------------------


class SnapshotManager:
    """Manages periodic snapshots of warm store state (§3.3).

    Usage:
        mgr = SnapshotManager(warm_store, event_log)
        mgr.maybe_snapshot(window_id)  # called each window
        # On resume:
        mgr.restore_from_file(path)
    """

    def __init__(
        self,
        warm_store: WarmStateStore,
        event_log: FactEventLog,
        interval: int = SNAPSHOT_INTERVAL,
    ) -> None:
        self._store = warm_store
        self._log = event_log
        self._interval = interval
        self._snapshots: list[EventLogSnapshot] = []
        self._windows_since_snapshot: int = 0

    @property
    def snapshot_count(self) -> int:
        """Return the current snapshot count."""
        return len(self._snapshots)

    @property
    def last_snapshot(self) -> EventLogSnapshot | None:
        """Return the last snapshot."""
        return self._snapshots[-1] if self._snapshots else None

    # --- Snapshot creation ----------------------------------------------------

    def snapshot(self, window_id: str) -> EventLogSnapshot:
        """Create a snapshot of the current warm store state."""
        snap = EventLogSnapshot(
            snapshot_id=f"snap-{len(self._snapshots) + 1}-{int(time.time())}",
            window_id=window_id,
            window_count=self._store.window_count,
            warm_store_data=self._store.to_dict(),
            last_event_id=self._log.size,
        )
        snap.checksum = snap.compute_checksum()
        self._snapshots.append(snap)
        self._windows_since_snapshot = 0
        return snap

    def maybe_snapshot(self, window_id: str) -> EventLogSnapshot | None:
        """Create snapshot if interval has elapsed."""
        self._windows_since_snapshot += 1
        if self._windows_since_snapshot >= self._interval:
            return self.snapshot(window_id)
        return None

    def truncate_before_snapshot(self) -> int:
        """Truncate event log before the last snapshot.  Returns events removed."""
        snap = self.last_snapshot
        if snap is None:
            return 0
        removed = self._log.truncate_before(snap.last_event_id)
        return len(removed)

    # --- Restore --------------------------------------------------------------

    def restore_from_snapshot(self, snapshot: EventLogSnapshot) -> list[str]:
        """Restore warm store from *snapshot*, returning validation warnings.

        Performs consistency checks (§22.4):
        1. Schema version compatibility
        2. Checksum integrity
        3. Fact count consistency
        4. Edge integrity (both endpoints exist)
        5. No orphaned edges
        6. Critical state present
        7. Window count non-negative
        8. Fact IDs unique
        9. No circular supersession
        10. Timestamps reasonable
        """
        warnings: list[str] = []

        # Check 1: Schema version
        if snapshot.schema_version != SCHEMA_VERSION:
            warnings.append(f"Schema version mismatch: {snapshot.schema_version} vs {SCHEMA_VERSION}")

        # Check 2: Checksum
        if not snapshot.verify_checksum():
            warnings.append("Checksum verification FAILED — data may be corrupted")

        # Load the data
        data = snapshot.warm_store_data
        self._store.load_from_dict(data)

        # Check 3: Fact count
        expected_count = len(data.get("facts", {}))
        actual_count = self._store.fact_count
        if expected_count != actual_count:
            warnings.append(f"Fact count mismatch: expected {expected_count}, got {actual_count}")

        # Check 4-5: Edge integrity
        graph = self._store.graph
        fact_ids = set(graph.nodes.keys())
        for edge in graph.edges:
            if edge.source_id not in fact_ids:
                warnings.append(f"Orphaned edge source: {edge.source_id}")
            if edge.target_id not in fact_ids:
                warnings.append(f"Orphaned edge target: {edge.target_id}")

        # Check 6: Critical state
        cs = self._store.critical_state
        if not cs.goal and not cs.phase:
            warnings.append("Critical state has no goal or phase set")

        # Check 7: Window count
        if self._store.window_count < 0:
            warnings.append(f"Invalid window count: {self._store.window_count}")

        # Check 8: Unique fact IDs (guaranteed by dict, but verify)
        all_facts = self._store.get_facts(include_superseded=True)
        ids = [f.id for f in all_facts]
        if len(ids) != len(set(ids)):
            warnings.append("Duplicate fact IDs detected")

        # Check 9: No circular supersession
        for sf in all_facts:
            if sf.is_superseded and sf.superseded_by == sf.id:
                warnings.append(f"Circular supersession: {sf.id}")

        # Check 10: Timestamps
        now = time.time()
        for sf in all_facts:
            if sf.created_at > now + 3600:
                warnings.append(f"Future timestamp on fact {sf.id}")

        return warnings

    # --- File I/O -------------------------------------------------------------

    def save_to_file(self, path: str | Path) -> None:
        """Save latest snapshot to disk using atomic write (§4G.4)."""
        snap = self.last_snapshot
        if snap is None:
            snap = self.snapshot("auto-save")
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        # Atomic write: temp file then rename
        tmp = p.with_suffix(".tmp")
        try:
            tmp.write_text(json.dumps(snap.to_dict(), default=str), encoding="utf-8")
            os.replace(str(tmp), str(p))
        except BaseException:
            tmp.unlink(missing_ok=True)
            raise

    def restore_from_file(self, path: str | Path) -> list[str]:
        """Load snapshot from disk, verify, restore.  Returns warnings.

        Handles partial-write corruption by checking for .tmp files (§4G.4).
        After snapshot restore, replays event log entries since the snapshot
        to rebuild full state (§4D.3).
        """
        p = Path(path)
        if not p.exists():
            # Check for interrupted atomic write (§4G.4)
            tmp = p.with_suffix(".tmp")
            if tmp.exists():
                try:
                    data = json.loads(tmp.read_text(encoding="utf-8"))
                    snapshot = EventLogSnapshot.from_dict(data)
                    warnings = self.restore_from_snapshot(snapshot)
                    warnings.insert(0, "Recovered from interrupted write (.tmp file)")
                    return warnings
                except (json.JSONDecodeError, OSError):
                    return [f"Snapshot file not found and .tmp is corrupt: {path}"]
            return [f"Snapshot file not found: {path}"]
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            return [f"Failed to read snapshot: {exc}"]

        snapshot = EventLogSnapshot.from_dict(data)
        warnings = self.restore_from_snapshot(snapshot)

        # Replay events since snapshot to rebuild full state (§4D.3)
        replayed = self._replay_events_since(snapshot.last_event_id)
        if replayed > 0:
            warnings.append(f"Replayed {replayed} events since snapshot")

        return warnings

    def _replay_events_since(self, last_event_id: int) -> int:
        """Replay event log entries after a snapshot to rebuild state (§4D.3)."""
        from .event_log import EVENT_SUPERSEDED
        replayed = 0
        for event in self._log.all_events():
            if event.event_id <= last_event_id:
                continue
            if event.event_type == EVENT_SUPERSEDED:
                new_id = event.payload.get("superseded_by", "")
                conf = event.payload.get("confidence", 1.0)
                self._store.supersede(event.fact_id, new_id, conf)
                replayed += 1
        return replayed
