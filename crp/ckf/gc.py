# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""CKF cross-session garbage collection (§3.8).

gc_score formula determines fact retention priority.
Tombstone → purge lifecycle.  Budget 500 MB, trigger 80%, target 70%.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from crp.state.fact import StateFact

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

BUDGET_BYTES = 500 * 1024 * 1024  # 500 MB
TRIGGER_RATIO = 0.80  # Trigger GC at 80% of budget
TARGET_RATIO = 0.70  # Reduce to 70% of budget
TOMBSTONE_AGE_WINDOWS = 50  # Windows before tombstone → purge


# ---------------------------------------------------------------------------
# GC score formula
# ---------------------------------------------------------------------------


def gc_score(fact: StateFact, current_window: int = 0) -> float:
    """Compute GC retention score for a fact.

    Higher score = more worth keeping.  Components:
    - Confidence: raw confidence value
    - Freshness: inverse of age (recently created facts score higher)
    - Usage: how many envelopes consumed this fact
    - Graph connectivity: number of edges (well-connected facts are more valuable)

    Formula:
        gc_score = 0.3 * confidence + 0.3 * freshness + 0.2 * usage + 0.2 * connectivity
    """
    confidence = min(1.0, fact.confidence or 0.0)

    # Freshness — decays with age; 1.0 at age 0, approaches 0 for old facts
    age = fact.age_in_windows
    freshness = 1.0 / (1.0 + age * 0.1)

    # Usage — normalised seen_count (cap at 20)
    usage = min(1.0, fact.seen_count / 20.0)

    # Connectivity — normalised edge count (cap at 10)
    connectivity = min(1.0, len(fact.graph_edges) / 10.0)

    return 0.3 * confidence + 0.3 * freshness + 0.2 * usage + 0.2 * connectivity


# ---------------------------------------------------------------------------
# GC result
# ---------------------------------------------------------------------------


@dataclass
class GCResult:
    """Result of a GC pass."""

    tombstoned: list[str] = field(default_factory=list)
    purged: list[str] = field(default_factory=list)
    bytes_freed_estimate: int = 0
    facts_before: int = 0
    facts_after: int = 0


# ---------------------------------------------------------------------------
# GarbageCollector
# ---------------------------------------------------------------------------


class GarbageCollector:
    """Cross-session GC for the CKF fact store.

    Lifecycle: active → tombstoned → purged.
    Tombstoned facts are excluded from retrieval but retained for
    TOMBSTONE_AGE_WINDOWS before final purge.
    """

    def __init__(
        self,
        budget_bytes: int = BUDGET_BYTES,
        trigger_ratio: float = TRIGGER_RATIO,
        target_ratio: float = TARGET_RATIO,
    ) -> None:
        self._budget = budget_bytes
        self._trigger = trigger_ratio
        self._target = target_ratio
        self._tombstones: dict[str, int] = {}  # fact_id → window when tombstoned

    def should_gc(self, estimated_bytes: int) -> bool:
        """Return True if GC should run (estimated usage ≥ trigger)."""
        return estimated_bytes >= int(self._budget * self._trigger)

    def run(
        self,
        facts: dict[str, StateFact],
        estimated_bytes: int,
        current_window: int = 0,
    ) -> GCResult:
        """Execute a GC pass.

        1. Purge old tombstones (aged out).
        2. If still over target, tombstone lowest-scoring active facts.
        """
        result = GCResult(facts_before=len(facts))
        target_bytes = int(self._budget * self._target)

        # --- Phase 1: Purge old tombstones ---
        to_purge: list[str] = []
        for fid, tombstone_window in list(self._tombstones.items()):
            if current_window - tombstone_window >= TOMBSTONE_AGE_WINDOWS:
                to_purge.append(fid)

        for fid in to_purge:
            if fid in facts:
                result.bytes_freed_estimate += self._estimate_fact_bytes(facts[fid])
                del facts[fid]
                result.purged.append(fid)
            self._tombstones.pop(fid, None)

        # Recalculate
        estimated_bytes -= result.bytes_freed_estimate

        # --- Phase 2: Tombstone low-value facts if still over target ---
        if estimated_bytes > target_bytes:
            # Score all active (non-tombstoned) facts
            active: list[tuple[float, str]] = []
            for fid, sf in facts.items():
                if fid not in self._tombstones and not sf.is_superseded:
                    active.append((gc_score(sf, current_window), fid))

            # Sort ascending — lowest score first (candidates for tombstoning)
            active.sort()

            for _score, fid in active:
                if estimated_bytes <= target_bytes:
                    break
                self._tombstones[fid] = current_window
                result.tombstoned.append(fid)
                estimated_bytes -= self._estimate_fact_bytes(facts[fid])

        result.facts_after = len(facts)
        return result

    def is_tombstoned(self, fact_id: str) -> bool:
        """Return True if *fact_id* is currently tombstoned."""
        return fact_id in self._tombstones

    def tombstone_count(self) -> int:
        """Return the number of currently tombstoned facts."""
        return len(self._tombstones)

    @staticmethod
    def _estimate_fact_bytes(sf: StateFact) -> int:
        """Rough byte estimate for a StateFact."""
        base = len(sf.text.encode("utf-8")) + 200  # overhead
        if sf.has_embedding():
            base += len(sf.embedding or []) * 4  # float32
        return base

    @staticmethod
    def estimate_store_bytes(facts: dict[str, StateFact]) -> int:
        """Estimate total bytes for the fact store."""
        total = 0
        for sf in facts.values():
            total += GarbageCollector._estimate_fact_bytes(sf)
        return total
