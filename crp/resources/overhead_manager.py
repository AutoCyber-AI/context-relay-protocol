# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Overhead budget manager — shedding cascade + lazy embedding (§6.12, §3.2).

OverheadBudgetManager sits on top of the existing ``OverheadBudget`` in
``cost_model.py`` and adds two features from the spec:

1. **Feature shedding cascade (§6.12)**
   When overhead exceeds the cap (default 15%), features are shed in a
   fixed cost order:

       community_detection  →  cross_encoder  →  gliner  →  uie  →  discourse

   Each feature can be individually disabled and later re-enabled when
   overhead drops.

2. **Lazy embedding batch (§3.2)**
   Instead of computing embeddings on every ``fact.created`` event,
   the manager *defers* them and batch-processes once N facts have
   accumulated or a flush is requested.

Design goals:
  * Pure logic — no external deps, no I/O.
  * Works with or without an EventEmitter.
  * Thread-safe (uses a threading.Lock around mutable state).
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("crp.overhead_manager")


# ═══════════════════════════════════════════════════════════════════════════
# Feature shedding cascade (§9.6a)
# ═══════════════════════════════════════════════════════════════════════════

# Ordered cheapest-to-most-expensive.
# First in the list = shed first when over budget.
SHEDDING_CASCADE: list[str] = [
    "community_detection",
    "cross_encoder",
    "gliner",
    "uie",
    "discourse",
]

# ML intelligence features that must NEVER be shed.  These are the core
# extraction pipeline stages that provide CRP's analytical intelligence.
# Under pressure, the system throttles throughput (fewer facts per stage,
# larger batches) rather than disabling these capabilities.
PROTECTED_INTELLIGENCE: frozenset[str] = frozenset({"gliner", "uie", "discourse"})


@dataclass
class SheddingState:
    """Tracks which features are currently enabled or shed."""

    enabled: dict[str, bool] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.enabled:
            self.enabled = {f: True for f in SHEDDING_CASCADE}


# ═══════════════════════════════════════════════════════════════════════════
# Lazy embedding batch (§9.6b)
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class _PendingEmbedding:
    """One deferred embedding request."""

    fact_id: str
    text: str


# ═══════════════════════════════════════════════════════════════════════════
# OverheadBudgetManager
# ═══════════════════════════════════════════════════════════════════════════


class OverheadBudgetManager:
    """Orchestrates feature shedding and lazy embedding batching.

    Usage::

        mgr = OverheadBudgetManager(max_overhead_pct=15, batch_size=32)

        # After each window, update overhead ratio:
        mgr.update_overhead(current_pct=12.5)
        assert mgr.is_feature_enabled("gliner")

        # When overhead spikes:
        mgr.update_overhead(current_pct=18.0)
        assert not mgr.is_feature_enabled("community_detection")  # shed first

        # Lazy embedding:
        mgr.defer_embedding("f1", "some fact text")
        mgr.defer_embedding("f2", "another fact text")
        batch = mgr.flush_embeddings()  # returns pending, clears queue
    """

    def __init__(
        self,
        max_overhead_pct: float = 15.0,
        batch_size: int = 32,
    ) -> None:
        self._lock = threading.Lock()
        self._max_pct = max_overhead_pct
        self._batch_size = batch_size
        self._shedding = SheddingState()
        self._pending: list[_PendingEmbedding] = []
        self._current_pct: float = 0.0
        self._shed_log: list[str] = []

    # -- shedding cascade -------------------------------------------------

    def update_overhead(self, current_pct: float) -> list[str]:
        """Update the current overhead percentage and shed/restore features.

        Returns a list of features that changed state (shed or restored).
        """
        with self._lock:
            self._current_pct = current_pct
            changed: list[str] = []

            if current_pct > self._max_pct:
                # Shed features cheapest-first until (conceptually) under budget.
                # PROTECTED_INTELLIGENCE features (gliner, uie, discourse) are
                # never shed — they are core ML extraction intelligence.
                for feat in SHEDDING_CASCADE:
                    if feat in PROTECTED_INTELLIGENCE:
                        continue  # never shed ML intelligence
                    if self._shedding.enabled[feat]:
                        self._shedding.enabled[feat] = False
                        msg = f"Shed {feat} (overhead {current_pct:.1f}% > {self._max_pct}%)"
                        logger.info(msg)
                        self._shed_log.append(msg)
                        changed.append(feat)
                        break  # shed one at a time per update call
            else:
                # Restore features most-expensive-first (reverse order).
                for feat in reversed(SHEDDING_CASCADE):
                    if feat in PROTECTED_INTELLIGENCE:
                        continue  # protected features are always on
                    if not self._shedding.enabled[feat]:
                        self._shedding.enabled[feat] = True
                        msg = f"Restored {feat} (overhead {current_pct:.1f}%)"
                        logger.info(msg)
                        changed.append(feat)
                        break

            return changed

    def is_feature_enabled(self, name: str) -> bool:
        """Check if a feature is currently enabled."""
        with self._lock:
            return self._shedding.enabled.get(name, True)

    @property
    def shed_log(self) -> list[str]:
        """Return the shed log."""
        with self._lock:
            return list(self._shed_log)

    @property
    def enabled_features(self) -> dict[str, bool]:
        """Return the enabled features."""
        with self._lock:
            return dict(self._shedding.enabled)

    # -- lazy embedding batch ---------------------------------------------

    def defer_embedding(self, fact_id: str, text: str) -> bool:
        """Queue a fact for deferred embedding.

        Returns ``True`` if the batch is now full and should be flushed.
        """
        with self._lock:
            self._pending.append(_PendingEmbedding(fact_id=fact_id, text=text))
            return len(self._pending) >= self._batch_size

    def flush_embeddings(self) -> list[tuple[str, str]]:
        """Return all pending embeddings as ``(fact_id, text)`` and clear queue."""
        with self._lock:
            batch = [(p.fact_id, p.text) for p in self._pending]
            self._pending.clear()
            return batch

    @property
    def pending_embedding_count(self) -> int:
        """Return the current pending embedding count."""
        with self._lock:
            return len(self._pending)

    # -- introspection ----------------------------------------------------

    @property
    def current_overhead_pct(self) -> float:
        """Return the current overhead pct."""
        return self._current_pct

    @property
    def max_overhead_pct(self) -> float:
        """Return the max overhead pct."""
        return self._max_pct

    def summary(self) -> dict[str, Any]:
        """Return a JSON-serializable summary of the manager state."""
        with self._lock:
            return {
                "current_overhead_pct": round(self._current_pct, 2),
                "max_overhead_pct": self._max_pct,
                "features": dict(self._shedding.enabled),
                "pending_embeddings": len(self._pending),
                "shed_log": list(self._shed_log),
            }
