# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Centralized resource manager — memory tracking, model registry, pressure (§audit R1).

Tracks memory consumption, ML model lifecycle, session budgets,
and provides pressure signals for adaptive dispatch behavior.

Pressure levels:
    "none"     : usage < 50% of budget → normal operation
    "low"      : 50-70% → compaction eligible
    "medium"   : 70-85% → aggressive compaction, idle model unload
    "high"     : 85-95% → forced compaction, model unload, GC
    "critical" : >95% → emergency cleanup, session pruning
"""

from __future__ import annotations

import gc
import logging
import os
import time
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Budget defaults
# ---------------------------------------------------------------------------

DEFAULT_MEMORY_BUDGET_MB = 512
PRESSURE_THRESHOLDS: list[tuple[str, float]] = [
    ("critical", 0.95),
    ("high", 0.85),
    ("medium", 0.70),
    ("low", 0.50),
    ("none", 0.0),
]

# Estimated per-model memory footprint (MB).
MODEL_ESTIMATES: dict[str, float] = {
    "sentence-transformers": 150.0,
    "cross-encoder": 200.0,
    "gliner": 200.0,
    "uie": 400.0,
    "hnsw-index": 50.0,  # varies with fact count
}

# Average bytes per fact in warm store (empirical).
_BYTES_PER_FACT = 500


@dataclass
class ResourceSnapshot:
    """Point-in-time resource utilization snapshot."""

    timestamp: float = 0.0
    process_rss_mb: float = 0.0
    crp_estimated_mb: float = 0.0
    model_memory_mb: float = 0.0
    fact_store_mb: float = 0.0
    budget_mb: float = DEFAULT_MEMORY_BUDGET_MB
    pressure_level: str = "none"
    models_loaded: list[str] = field(default_factory=list)
    fact_count: int = 0
    session_count: int = 0

    @property
    def utilization_ratio(self) -> float:
        """Return the utilization ratio."""
        if self.budget_mb <= 0:
            return 0.0
        return self.crp_estimated_mb / self.budget_mb


@dataclass
class ModelEntry:
    """Registered ML model with lifecycle tracking."""

    name: str
    estimated_mb: float
    loaded_at: float = 0.0
    last_used_at: float = 0.0
    use_count: int = 0
    is_loaded: bool = False


class ResourceManager:
    """Centralized resource tracking and pressure management.

    Usage::

        rm = ResourceManager(budget_mb=512)
        rm.register_model("sentence-transformers", 150)
        rm.mark_model_loaded("sentence-transformers")
        snap = rm.snapshot()
        print(snap.pressure_level)
    """

    def __init__(self, budget_mb: float = DEFAULT_MEMORY_BUDGET_MB) -> None:
        self._budget_mb = budget_mb
        self._models: dict[str, ModelEntry] = {}
        self._fact_count = 0
        self._session_count = 0
        self._created_at = time.time()
        self._last_gc = 0.0
        self._cleanup_count = 0

    # -- Model lifecycle ---------------------------------------------------

    def register_model(self, name: str, estimated_mb: float) -> None:
        """Register an ML model (call at init, before loading)."""
        self._models[name] = ModelEntry(name=name, estimated_mb=estimated_mb)

    def mark_model_loaded(self, name: str) -> None:
        """Mark a model as loaded into memory."""
        if name in self._models:
            self._models[name].is_loaded = True
            self._models[name].loaded_at = time.time()
            self._models[name].last_used_at = time.time()

    def mark_model_used(self, name: str) -> None:
        """Record model usage (resets idle timer)."""
        if name in self._models:
            self._models[name].last_used_at = time.time()
            self._models[name].use_count += 1

    def mark_model_unloaded(self, name: str) -> None:
        """Mark a model as unloaded from memory."""
        if name in self._models:
            self._models[name].is_loaded = False

    # -- Fact store tracking -----------------------------------------------

    def update_fact_count(self, count: int) -> None:
        """Update the tracked fact-store fact count."""
        self._fact_count = count

    def update_session_count(self, count: int) -> None:
        """Update the tracked active session count."""
        self._session_count = count

    # -- Snapshot & pressure -----------------------------------------------

    def snapshot(self) -> ResourceSnapshot:
        """Take a point-in-time resource snapshot."""
        model_mb = sum(m.estimated_mb for m in self._models.values() if m.is_loaded)
        fact_mb = self._fact_count * _BYTES_PER_FACT / (1024 * 1024)
        crp_mb = model_mb + fact_mb

        rss_mb = _get_process_rss_mb()
        pressure = self._compute_pressure(crp_mb)
        loaded = [m.name for m in self._models.values() if m.is_loaded]

        return ResourceSnapshot(
            timestamp=time.time(),
            process_rss_mb=round(rss_mb, 1),
            crp_estimated_mb=round(crp_mb, 1),
            model_memory_mb=round(model_mb, 1),
            fact_store_mb=round(fact_mb, 3),
            budget_mb=self._budget_mb,
            pressure_level=pressure,
            models_loaded=loaded,
            fact_count=self._fact_count,
            session_count=self._session_count,
        )

    def _compute_pressure(self, crp_mb: float) -> str:
        if self._budget_mb <= 0:
            return "none"
        ratio = crp_mb / self._budget_mb
        for name, threshold in PRESSURE_THRESHOLDS:
            if ratio >= threshold:
                return name
        return "none"

    # -- Cleanup actions ---------------------------------------------------

    def should_cleanup(self) -> bool:
        """Return True if pressure warrants cleanup actions."""
        snap = self.snapshot()
        return snap.pressure_level in ("medium", "high", "critical")

    def run_gc(self) -> int:
        """Run Python garbage collection and return the number of objects collected."""
        collected = gc.collect()
        self._last_gc = time.time()
        self._cleanup_count += 1
        logger.debug("GC collected %d objects (run #%d)", collected, self._cleanup_count)
        return collected

    def get_idle_models(self, idle_seconds: float = 300.0) -> list[str]:
        """Return names of loaded models idle for longer than *idle_seconds*.

        Args:
            idle_seconds: Idle threshold in seconds.

        Returns:
            List of model names eligible for unload.
        """
        now = time.time()
        return [
            m.name for m in self._models.values()
            if m.is_loaded and (now - m.last_used_at) > idle_seconds
        ]

    def mark_unloaded(self, model_name: str) -> None:
        """Mark a model as unloaded (freed from memory)."""
        if model_name in self._models:
            self._models[model_name].is_loaded = False
            logger.info("Model marked unloaded: %s", model_name)

    def trigger_gc(self) -> int:
        """Run GC if pressure warrants it (alias for should_cleanup + run_gc)."""
        if self.should_cleanup():
            return self.run_gc()
        return 0

    # -- Summary -----------------------------------------------------------

    def summary(self) -> dict:
        """Return a human-readable resource utilization summary dict."""
        snap = self.snapshot()
        return {
            "budget_mb": self._budget_mb,
            "crp_estimated_mb": snap.crp_estimated_mb,
            "model_memory_mb": snap.model_memory_mb,
            "fact_store_mb": snap.fact_store_mb,
            "process_rss_mb": snap.process_rss_mb,
            "pressure_level": snap.pressure_level,
            "utilization_pct": round(snap.utilization_ratio * 100, 1),
            "models_loaded": snap.models_loaded,
            "fact_count": snap.fact_count,
            "gc_runs": self._cleanup_count,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_process_rss_mb() -> float:
    """Get process RSS in MB (best-effort, returns 0 on failure)."""
    try:
        if os.name == "nt":
            import ctypes
            import ctypes.wintypes

            class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
                _fields_ = [
                    ("cb", ctypes.wintypes.DWORD),
                    ("PageFaultCount", ctypes.wintypes.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t),
                ]

            pmc = PROCESS_MEMORY_COUNTERS()
            pmc.cb = ctypes.sizeof(pmc)
            kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
            handle = kernel32.GetCurrentProcess()
            psapi = ctypes.windll.psapi  # type: ignore[attr-defined]
            if psapi.GetProcessMemoryInfo(handle, ctypes.byref(pmc), pmc.cb):
                return pmc.WorkingSetSize / (1024 * 1024)
        else:
            with open("/proc/self/status") as f:
                for line in f:
                    if line.startswith("VmRSS:"):
                        return int(line.split()[1]) / 1024
    except Exception:
        pass
    return 0.0
