# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Adaptive resource allocator — efficient CRP pipeline without cutting intelligence.

Integrates ResourceManager (memory pressure) with OverheadBudgetManager
(feature shedding) to dynamically adapt CRP's processing pipeline based
on real-time performance measurements.

Design philosophy:
  CRP is an EFFICIENCY protocol, not a speed protocol.  ML extraction
  stages (GLiNER, UIE, Discourse) are core intelligence and are NEVER
  disabled.  Under pressure, the system *throttles throughput* (fewer
  facts per stage, larger batches, prompt caching) rather than cutting
  analytical capability.

Design goals:
  1. Keep CRP overhead below a configurable cap (default 15% of wall time)
  2. Shed optional optimization features under pressure (community detection,
     cross-encoder reranking) while protecting ML intelligence
  3. Throttle throughput gracefully: reduce fact counts, increase batches
  4. Provide prompt-level efficiency hints (caching, dedup, connection reuse)
  5. Track per-window overhead history and adapt thresholds
  6. Provide hardware-aware defaults (CPU count, available RAM)

Efficiency strategies (applied in order of priority):
  Phase 1 — Prompt efficiency (caching, deduplication, connection reuse)
  Phase 2 — Feature shedding (community_detection, cross_encoder only)
  Phase 3 — Throughput throttling (reduce facts per stage, larger batches)
  Phase 4 — Model lifecycle (idle models freed after timeout)
  Phase 5 — GC sweep (Python garbage collection under memory pressure)
"""

from __future__ import annotations

import logging
import os
import time
import threading
from dataclasses import dataclass, field

from crp.resources.overhead_manager import OverheadBudgetManager, SHEDDING_CASCADE, PROTECTED_INTELLIGENCE
from crp.resources.resource_manager import ResourceManager

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# Hardware detection
# ═══════════════════════════════════════════════════════════════════════════

def detect_hardware() -> dict[str, int | float]:
    """Detect available hardware resources (best-effort)."""
    cpu_count = os.cpu_count() or 1
    try:
        if os.name == "nt":
            import ctypes
            kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]

            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            mem = MEMORYSTATUSEX()
            mem.dwLength = ctypes.sizeof(mem)
            kernel32.GlobalMemoryStatusEx(ctypes.byref(mem))
            total_ram_mb = mem.ullTotalPhys / (1024 * 1024)
            available_ram_mb = mem.ullAvailPhys / (1024 * 1024)
        else:
            with open("/proc/meminfo") as f:
                info = {}
                for line in f:
                    parts = line.split()
                    if len(parts) >= 2:
                        info[parts[0].rstrip(":")] = int(parts[1])
            total_ram_mb = info.get("MemTotal", 0) / 1024
            available_ram_mb = info.get("MemAvailable", info.get("MemFree", 0)) / 1024
    except Exception:
        total_ram_mb = 0.0
        available_ram_mb = 0.0

    return {
        "cpu_count": cpu_count,
        "total_ram_mb": round(total_ram_mb),
        "available_ram_mb": round(available_ram_mb),
    }


# ═══════════════════════════════════════════════════════════════════════════
# Overhead history tracker
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class WindowOverheadRecord:
    """Per-window overhead measurement."""
    window_index: int = 0
    total_ms: float = 0.0
    llm_ms: float = 0.0
    overhead_ms: float = 0.0
    overhead_pct: float = 0.0
    envelope_ms: float = 0.0
    extraction_ms: float = 0.0
    features_shed: list[str] = field(default_factory=list)
    stages_skipped: list[int] = field(default_factory=list)


# ═══════════════════════════════════════════════════════════════════════════
# Extraction profile — what stages to run
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class ExtractionProfile:
    """Recommended extraction configuration based on resource state."""
    enable_stage_3: bool = True   # GLiNER NER
    enable_stage_4: bool = True   # UIE relation extraction
    enable_stage_5: bool = True   # Discourse analysis
    enable_stage_6: bool = False  # LLM-assisted (always off by default)
    max_facts_per_stage: int = 200


@dataclass
class EnvelopeProfile:
    """Recommended envelope configuration based on resource state."""
    enable_cross_encoder: bool = True
    enable_ckf: bool = True
    max_packing_facts: int = 500
    embedding_batch_size: int = 32


@dataclass
class PromptEfficiency:
    """LLM-side efficiency recommendations based on pipeline state.

    These hints allow providers to optimize token usage, connection
    management, and prompt caching — reducing cost and latency without
    cutting any intelligence features.
    """
    deduplicate_facts: bool = True
    cache_system_prompt: bool = True
    compress_envelope: bool = False
    reuse_connection: bool = True
    estimated_cache_hit_pct: float = 0.0


# Throughput levels — graceful throttling without cutting intelligence
THROUGHPUT_NORMAL = "normal"
THROUGHPUT_THROTTLED = "throttled"
THROUGHPUT_CONSTRAINED = "constrained"

# Facts-per-stage at each throughput level
_THROUGHPUT_FACTS: dict[str, int] = {
    THROUGHPUT_NORMAL: 200,
    THROUGHPUT_THROTTLED: 150,
    THROUGHPUT_CONSTRAINED: 100,
}

# Embedding batch sizes at each throughput level
_THROUGHPUT_BATCH: dict[str, int] = {
    THROUGHPUT_NORMAL: 32,
    THROUGHPUT_THROTTLED: 48,
    THROUGHPUT_CONSTRAINED: 64,
}

# Max packing facts at each throughput level
_THROUGHPUT_PACKING: dict[str, int] = {
    THROUGHPUT_NORMAL: 500,
    THROUGHPUT_THROTTLED: 350,
    THROUGHPUT_CONSTRAINED: 200,
}


# ═══════════════════════════════════════════════════════════════════════════
# Adaptive Allocator
# ═══════════════════════════════════════════════════════════════════════════


class AdaptiveAllocator:
    """Dynamically tunes CRP pipeline based on real-time overhead and pressure.

    The allocator observes per-window overhead ratios and resource pressure,
    then adjusts throughput parameters and prompt efficiency hints to keep
    overhead below the configured cap.

    Core principle: ML extraction stages (GLiNER, UIE, Discourse) are
    NEVER disabled — they are the protocol's core intelligence.  Under
    pressure, the system reduces fact counts and increases batch sizes
    (graceful throttling) rather than cutting analytical capability.

    Usage::

        alloc = AdaptiveAllocator(
            resource_manager=rm,
            overhead_manager=om,
            overhead_cap_pct=15.0,
        )

        # Before each dispatch — get recommended profiles
        ext_profile = alloc.extraction_profile()
        env_profile = alloc.envelope_profile()
        efficiency = alloc.prompt_efficiency()

        # After each dispatch — record overhead
        alloc.record_window(total_ms=1200, llm_ms=1050,
                            envelope_ms=80, extraction_ms=50)

        # Cleanup check
        if alloc.should_unload_models():
            for model in alloc.idle_models():
                unload(model)
    """

    # Overhead smoothing: EWMA decay factor (0.3 = recent windows weighted more)
    _EWMA_ALPHA = 0.3

    # How many consecutive windows over cap before constrained throughput
    _CONSECUTIVE_OVER_LIMIT = 3

    def __init__(
        self,
        resource_manager: ResourceManager,
        overhead_manager: OverheadBudgetManager,
        *,
        overhead_cap_pct: float = 15.0,
        idle_model_timeout_s: float = 300.0,
        max_history: int = 50,
    ) -> None:
        self._rm = resource_manager
        self._om = overhead_manager
        self._cap = overhead_cap_pct
        self._idle_timeout = idle_model_timeout_s
        self._lock = threading.Lock()

        # Overhead history
        self._history: list[WindowOverheadRecord] = []
        self._max_history = max_history
        self._window_count = 0

        # EWMA smoothed overhead
        self._ewma_overhead_pct: float = 0.0

        # Consecutive windows over cap
        self._consecutive_over: int = 0

        # Throughput level — graceful throttling (never disables ML stages)
        self._throughput_level: str = THROUGHPUT_NORMAL

        # Hardware snapshot
        self._hardware = detect_hardware()

        logger.info(
            "AdaptiveAllocator initialized: cap=%.1f%%, hardware=%s",
            overhead_cap_pct, self._hardware,
        )

    # -- Record overhead per window ----------------------------------------

    def record_window(
        self,
        total_ms: float,
        llm_ms: float,
        *,
        envelope_ms: float = 0.0,
        extraction_ms: float = 0.0,
    ) -> WindowOverheadRecord:
        """Record overhead from a completed window and adapt."""
        overhead_ms = total_ms - llm_ms
        overhead_pct = (overhead_ms / total_ms * 100) if total_ms > 0 else 0.0

        with self._lock:
            self._window_count += 1

            # Update EWMA
            if self._window_count == 1:
                self._ewma_overhead_pct = overhead_pct
            else:
                self._ewma_overhead_pct = (
                    self._EWMA_ALPHA * overhead_pct
                    + (1 - self._EWMA_ALPHA) * self._ewma_overhead_pct
                )

            # Track consecutive over-cap windows
            if overhead_pct > self._cap:
                self._consecutive_over += 1
            else:
                self._consecutive_over = 0

            # Build record
            record = WindowOverheadRecord(
                window_index=self._window_count,
                total_ms=round(total_ms, 1),
                llm_ms=round(llm_ms, 1),
                overhead_ms=round(overhead_ms, 1),
                overhead_pct=round(overhead_pct, 1),
                envelope_ms=round(envelope_ms, 1),
                extraction_ms=round(extraction_ms, 1),
                features_shed=[
                    f for f in SHEDDING_CASCADE
                    if f not in PROTECTED_INTELLIGENCE
                    and not self._om.is_feature_enabled(f)
                ],
                stages_skipped=[],  # ML stages are never skipped
            )
            self._history.append(record)
            if len(self._history) > self._max_history:
                self._history.pop(0)

            # Update overhead manager
            self._om.update_overhead(overhead_pct)

            # Adapt throughput level (never disables ML stages)
            self._adapt_throughput(overhead_pct)

        return record

    # -- Adaptive throughput scheduling ------------------------------------

    def _adapt_throughput(self, overhead_pct: float) -> None:
        """Adjust throughput level based on overhead trend.

        Unlike stage disabling, this NEVER cuts ML intelligence features.
        Instead it reduces fact counts and increases batch sizes to keep
        overhead under cap while maintaining the full extraction pipeline.
        """
        if self._consecutive_over >= self._CONSECUTIVE_OVER_LIMIT:
            # Sustained over-cap: constrain throughput
            if self._throughput_level != THROUGHPUT_CONSTRAINED:
                self._throughput_level = THROUGHPUT_CONSTRAINED
                logger.info(
                    "Adaptive: throughput → constrained "
                    "(consecutive over cap: %d, ewma=%.1f%%)",
                    self._consecutive_over, self._ewma_overhead_pct,
                )
        elif overhead_pct > self._cap:
            # Single window over cap: throttle
            if self._throughput_level == THROUGHPUT_NORMAL:
                self._throughput_level = THROUGHPUT_THROTTLED
                logger.info(
                    "Adaptive: throughput → throttled "
                    "(overhead=%.1f%% > cap=%.1f%%)",
                    overhead_pct, self._cap,
                )
        elif self._ewma_overhead_pct < self._cap * 0.7:
            # Well under budget: restore throughput one step
            if self._throughput_level == THROUGHPUT_CONSTRAINED:
                self._throughput_level = THROUGHPUT_THROTTLED
                logger.info(
                    "Adaptive: throughput → throttled (restoring, ewma=%.1f%%)",
                    self._ewma_overhead_pct,
                )
            elif self._throughput_level == THROUGHPUT_THROTTLED:
                self._throughput_level = THROUGHPUT_NORMAL
                logger.info(
                    "Adaptive: throughput → normal (restored, ewma=%.1f%%)",
                    self._ewma_overhead_pct,
                )

    # -- Profile generation ------------------------------------------------

    def extraction_profile(self) -> ExtractionProfile:
        """Get recommended extraction profile based on current state.

        ML stages (3=GLiNER, 4=UIE, 5=Discourse) are ALWAYS enabled.
        Under pressure, throughput is throttled via max_facts_per_stage.
        """
        with self._lock:
            pressure = self._rm.snapshot().pressure_level

            # ML stages are ALWAYS enabled — they are core intelligence
            profile = ExtractionProfile(
                enable_stage_3=True,   # GLiNER NER — always on
                enable_stage_4=True,   # UIE relation extraction — always on
                enable_stage_5=True,   # Discourse analysis — always on
                enable_stage_6=False,  # LLM-assisted — off by default
            )

            # Throttle throughput based on pressure + throughput level
            if pressure in ("high", "critical"):
                profile.max_facts_per_stage = _THROUGHPUT_FACTS[THROUGHPUT_CONSTRAINED]
            elif pressure == "medium":
                profile.max_facts_per_stage = _THROUGHPUT_FACTS[THROUGHPUT_THROTTLED]
            else:
                profile.max_facts_per_stage = _THROUGHPUT_FACTS[self._throughput_level]

            return profile

    def envelope_profile(self) -> EnvelopeProfile:
        """Get recommended envelope profile based on current state.

        CKF (Contextual Knowledge Fusion) is ALWAYS enabled — it is
        core to CRP's knowledge retrieval.  Under pressure, batch sizes
        increase and packing limits decrease to reduce overhead.
        """
        with self._lock:
            pressure = self._rm.snapshot().pressure_level

            profile = EnvelopeProfile(
                enable_cross_encoder=self._om.is_feature_enabled("cross_encoder"),
                enable_ckf=True,  # CKF is always enabled — core intelligence
                max_packing_facts=_THROUGHPUT_PACKING[self._throughput_level],
                embedding_batch_size=_THROUGHPUT_BATCH[self._throughput_level],
            )

            # Pressure overrides: tighter limits but CKF stays on
            if pressure in ("high", "critical"):
                profile.max_packing_facts = _THROUGHPUT_PACKING[THROUGHPUT_CONSTRAINED]
                profile.embedding_batch_size = _THROUGHPUT_BATCH[THROUGHPUT_CONSTRAINED]
            elif pressure == "medium":
                profile.max_packing_facts = _THROUGHPUT_PACKING[THROUGHPUT_THROTTLED]
                profile.embedding_batch_size = _THROUGHPUT_BATCH[THROUGHPUT_THROTTLED]

            # If cross_encoder was shed by OverheadBudgetManager, respect that
            if not self._om.is_feature_enabled("cross_encoder"):
                profile.enable_cross_encoder = False

            return profile

    # -- Model lifecycle decisions -----------------------------------------

    def should_unload_models(self) -> bool:
        """Check if idle models should be unloaded."""
        pressure = self._rm.snapshot().pressure_level
        if pressure in ("high", "critical"):
            return True
        idle = self._rm.get_idle_models(self._idle_timeout)
        return len(idle) > 0

    def idle_models(self) -> list[str]:
        """Get list of models eligible for unloading."""
        pressure = self._rm.snapshot().pressure_level
        if pressure == "critical":
            # Under critical pressure, use shorter timeout
            return self._rm.get_idle_models(self._idle_timeout / 3)
        return self._rm.get_idle_models(self._idle_timeout)

    def should_run_gc(self) -> bool:
        """Check if garbage collection should run."""
        pressure = self._rm.snapshot().pressure_level
        return pressure in ("medium", "high", "critical")

    # -- Overhead queries --------------------------------------------------

    @property
    def ewma_overhead_pct(self) -> float:
        """Return the ewma overhead pct."""
        return self._ewma_overhead_pct

    @property
    def window_count(self) -> int:
        """Return the current window count."""
        return self._window_count

    @property
    def consecutive_over_cap(self) -> int:
        """Return the consecutive over cap."""
        return self._consecutive_over

    @property
    def disabled_stages(self) -> set[int]:
        """ML stages are never disabled — always returns empty set."""
        return set()

    @property
    def throughput_level(self) -> str:
        """Current throughput level: normal, throttled, or constrained."""
        return self._throughput_level

    @property
    def hardware(self) -> dict[str, int | float]:
        """Return the hardware."""
        return dict(self._hardware)

    def overhead_trend(self, last_n: int = 5) -> list[float]:
        """Return recent overhead percentages."""
        with self._lock:
            return [r.overhead_pct for r in self._history[-last_n:]]

    # -- Prompt efficiency -------------------------------------------------

    def prompt_efficiency(self) -> PromptEfficiency:
        """Get LLM prompt efficiency recommendations.

        After 2+ windows the system prompt is stable and should be cached.
        Under constrained throughput, envelope compression is recommended.
        """
        with self._lock:
            cache_enabled = self._window_count >= 2
            compress = self._throughput_level == THROUGHPUT_CONSTRAINED
            cache_pct = min(90.0, self._window_count * 15.0) if cache_enabled else 0.0

            return PromptEfficiency(
                deduplicate_facts=True,
                cache_system_prompt=cache_enabled,
                compress_envelope=compress,
                reuse_connection=True,
                estimated_cache_hit_pct=round(cache_pct, 1),
            )

    # -- Summary -----------------------------------------------------------

    def summary(self) -> dict:
        """Full allocator state for diagnostics."""
        with self._lock:
            return {
                "overhead_cap_pct": self._cap,
                "ewma_overhead_pct": round(self._ewma_overhead_pct, 1),
                "window_count": self._window_count,
                "consecutive_over_cap": self._consecutive_over,
                "throughput_level": self._throughput_level,
                "disabled_stages": [],  # ML stages are never disabled
                "hardware": self._hardware,
                "feature_shedding": self._om.enabled_features,
                "resource_pressure": self._rm.snapshot().pressure_level,
                "overhead_trend": [r.overhead_pct for r in self._history[-10:]],
                "prompt_efficiency": {
                    "cache_system_prompt": self._window_count >= 2,
                    "estimated_cache_hit_pct": round(
                        min(90.0, self._window_count * 15.0)
                        if self._window_count >= 2 else 0.0, 1,
                    ),
                },
            }
